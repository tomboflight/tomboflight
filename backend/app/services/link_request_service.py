from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.core.package_catalog import get_package
from app.core.relationship_catalog import (
    LINKED_HOUSEHOLD_RELATIONSHIP_TYPE,
)
from app.database import get_database
from app.schemas.link_request import LinkRequestCreate
from app.services.entitlement_service import resolve_project_entitlements
from app.services.audit_log_service import create_audit_log
from app.services.link_key_service import (
    get_active_key_doc_for_project,
    get_key_doc_by_value,
    get_project_summary,
    list_accessible_link_key_project_ids,
    project_supports_link_keys,
    user_can_access_project,
)


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _to_object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _requests_collection():
    db = get_database()
    return db["link_requests"]


def _household_links_collection():
    db = get_database()
    return db["household_links"]


def _projects_collection():
    db = get_database()
    return db["projects"]


def _households_collection():
    db = get_database()
    return db["households"]


def _entitlements_collection():
    db = get_database()
    return db["project_entitlements"]


def _normalize_value(value: Any) -> str:
    return str(value or "").strip()


def _project_id_candidates(project_id: str) -> list[Any]:
    candidates: list[Any] = [str(project_id)]
    object_id = _to_object_id(project_id)
    if object_id is not None:
        candidates.append(object_id)
    return candidates


def _project_object_id_candidates(project_id: str) -> list[ObjectId]:
    object_id = _to_object_id(project_id)
    return [object_id] if object_id is not None else []


def _project_entitlement(project_id: str) -> dict[str, Any] | None:
    query = {"project_id": {"$in": _project_id_candidates(project_id)}}
    return _entitlements_collection().find_one(
        {
            **query,
            "status": "active",
        }
    ) or _entitlements_collection().find_one(query)


def _resolve_project_link_scope(project_id: str) -> dict[str, Any]:
    summary = get_project_summary(project_id) or {}
    entitlement = _project_entitlement(project_id) or {}
    package_code = _normalize_value(
        entitlement.get("package_code") or summary.get("package_code")
    )
    active_addons = list(entitlement.get("active_addons") or [])

    resolved: dict[str, Any] = {}
    embedded_resolved = entitlement.get("resolved_entitlements")
    if isinstance(embedded_resolved, dict) and embedded_resolved:
        resolved = embedded_resolved

    if not resolved and package_code:
        try:
            resolved = resolve_project_entitlements(package_code, active_addons)
        except Exception:
            resolved = {}

    if not resolved and package_code:
        resolved = get_package(package_code) or {}

    max_households = int(resolved.get("max_households") or 0)
    max_family_branches = int(resolved.get("max_family_branches") or 0)
    effective_max_households = (
        max_family_branches if max_family_branches > 0 else max_households
    )
    return {
        "can_link_households": bool(resolved.get("can_link_households")),
        "max_households": max(0, effective_max_households),
    }


def _household_ids_for_project(project_id: str) -> set[str]:
    household_ids: set[str] = set()
    summary = get_project_summary(project_id) or {}
    summary_household_id = _normalize_value(summary.get("household_id"))
    if summary_household_id:
        household_ids.add(summary_household_id)

    project = _projects_collection().find_one(
        {
            "_id": {"$in": _project_object_id_candidates(project_id)}
        }
    )
    project_household_id = _normalize_value((project or {}).get("household_id"))
    if project_household_id:
        household_ids.add(project_household_id)

    households = _households_collection().find(
        {"project_id": {"$in": _project_id_candidates(project_id)}}
    )
    for household in households:
        for candidate in (
            _normalize_value(household.get("household_id")),
            _normalize_value(household.get("_id")),
        ):
            if candidate:
                household_ids.add(candidate)

    return household_ids


def _linked_household_component(seed_household_ids: set[str]) -> set[str]:
    if not seed_household_ids:
        return set()

    visited: set[str] = set()
    queue = list(seed_household_ids)

    while queue:
        current = _normalize_value(queue.pop(0))
        if not current or current in visited:
            continue
        visited.add(current)

        links = _household_links_collection().find(
            {
                "$or": [
                    {"source_household_id": current, "link_status": "approved"},
                    {"target_household_id": current, "link_status": "approved"},
                ]
            }
        )
        for link in links:
            source_id = _normalize_value(link.get("source_household_id"))
            target_id = _normalize_value(link.get("target_household_id"))
            if source_id and source_id not in visited:
                queue.append(source_id)
            if target_id and target_id not in visited:
                queue.append(target_id)

    return visited


def _assert_household_branch_capacity(source_project_id: str, target_project_id: str) -> None:
    source_scope = _resolve_project_link_scope(source_project_id)
    target_scope = _resolve_project_link_scope(target_project_id)

    if not source_scope.get("can_link_households"):
        raise ValueError(
            "The requesting workspace package does not include linked-household structure."
        )
    if not target_scope.get("can_link_households"):
        raise ValueError(
            "The receiving workspace package does not include linked-household structure."
        )

    source_component = _linked_household_component(
        _household_ids_for_project(source_project_id)
    )
    target_component = _linked_household_component(
        _household_ids_for_project(target_project_id)
    )
    merged_households = source_component | target_component

    for side, scope in (("requesting", source_scope), ("receiving", target_scope)):
        max_households = int(scope.get("max_households") or 0)
        if max_households > 0 and len(merged_households) > max_households:
            raise ValueError(
                f"Linking these branches would exceed the {side} workspace branch limit ({max_households})."
            )


def _enrich_request(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return None

    source_summary = get_project_summary(str(document.get("source_project_id") or ""))
    target_summary = get_project_summary(str(document.get("target_project_id") or ""))

    result = dict(document)
    if source_summary:
        result["source_project_name"] = source_summary.get("project_name")
        result["source_owner_email"] = source_summary.get("owner_email")
        result["source_package_code"] = source_summary.get("package_code")
        result["source_package_name"] = source_summary.get("package_name")
        result["source_household_id"] = source_summary.get("household_id")
    if target_summary:
        result["target_project_name"] = target_summary.get("project_name")
        result["target_owner_email"] = target_summary.get("owner_email")
        result["target_package_code"] = target_summary.get("package_code")
        result["target_package_name"] = target_summary.get("package_name")
        result["target_household_id"] = target_summary.get("household_id")

    return result


def list_link_requests() -> list[dict]:
    cursor = _requests_collection().find().sort("created_at", -1)
    return [item for item in (_enrich_request(doc) for doc in cursor) if item is not None]


def list_link_requests_for_user(
    user_id: str,
    *,
    user_email: str = "",
    project_id: str | None = None,
    direction: str = "all",
    status: str | None = None,
) -> list[dict]:
    if project_id:
        if not user_can_access_project(project_id, user_id, user_email):
            return []
        owned_project_ids = [str(project_id)]
    else:
        owned_project_ids = list_accessible_link_key_project_ids(user_id, user_email)

    if not owned_project_ids:
        return []

    direction_value = str(direction or "all").strip().lower()
    query: dict[str, Any] = {}

    if direction_value == "incoming":
        query["target_project_id"] = {"$in": owned_project_ids}
    elif direction_value == "outgoing":
        query["source_project_id"] = {"$in": owned_project_ids}
    else:
        query["$or"] = [
            {"source_project_id": {"$in": owned_project_ids}},
            {"target_project_id": {"$in": owned_project_ids}},
        ]

    if status:
        query["status"] = str(status).strip().lower()

    cursor = _requests_collection().find(query).sort("created_at", -1)
    return [item for item in (_enrich_request(doc) for doc in cursor) if item is not None]


def create_link_request(
    payload: LinkRequestCreate,
    *,
    requested_by: str,
    requested_by_user_id: str,
    requested_by_user_email: str = "",
) -> dict:
    source_project_id = str(payload.source_project_id or "").strip()
    target_key = str(payload.target_key or "").strip()

    if not user_can_access_project(
        source_project_id,
        requested_by_user_id,
        requested_by_user_email,
    ):
        raise PermissionError("Not authorized to create a link request for this project.")

    if not project_supports_link_keys(source_project_id):
        raise ValueError("Your package does not include link capabilities.")

    source_project = get_project_summary(source_project_id)
    if not source_project:
        raise ValueError("Source project not found.")

    source_key_doc = get_active_key_doc_for_project(source_project_id)
    if source_key_doc is None:
        raise ValueError("Generate a link key for your workspace before requesting a link.")
    if _normalize_value(source_key_doc.get("key_type") or "branch_link_key") != "branch_link_key":
        raise ValueError("The active source key must be a branch link key.")

    target_key_doc = get_key_doc_by_value(target_key)
    if target_key_doc is None:
        try:
            create_audit_log(
                "link_key_failed_use",
                str(requested_by_user_id or "").strip() or None,
                "project_link_key",
                _normalize_value(target_key)[:24],
                {"source_project_id": source_project_id},
            )
        except Exception:
            pass
        raise ValueError("Target link key was not found or is no longer active.")
    if _normalize_value(target_key_doc.get("key_type") or "branch_link_key") != "branch_link_key":
        raise ValueError("The target key must be a branch link key.")

    target_project_id = str(target_key_doc.get("project_id") or "").strip()
    if not target_project_id:
        raise ValueError("Target link key is invalid.")

    if source_project_id == target_project_id:
        raise ValueError("You cannot link a project to itself.")

    if not project_supports_link_keys(target_project_id):
        raise ValueError("The target workspace does not support link capabilities.")

    target_project = get_project_summary(target_project_id)
    if not target_project:
        raise ValueError("Target project not found.")

    _assert_household_branch_capacity(source_project_id, target_project_id)

    existing = _requests_collection().find_one(
        {
            "status": {"$in": ["pending", "approved"]},
            "$or": [
                {
                    "source_project_id": source_project_id,
                    "target_project_id": target_project_id,
                },
                {
                    "source_project_id": target_project_id,
                    "target_project_id": source_project_id,
                },
            ],
        }
    )
    if existing is not None:
        raise ValueError("A pending or approved link already exists between these workspaces.")

    data = {
        "source_project_id": source_project_id,
        "target_project_id": target_project_id,
        "source_household_id": source_project.get("household_id"),
        "target_household_id": target_project.get("household_id"),
        "source_key": str(source_key_doc.get("key_value") or ""),
        "target_key": str(target_key_doc.get("key_value") or ""),
        "source_key_hash": _normalize_value(source_key_doc.get("key_hash")),
        "target_key_hash": _normalize_value(target_key_doc.get("key_hash")),
        "status": "pending",
        "requested_by": str(requested_by or "").strip() or "Unknown User",
        "requested_by_user_id": str(requested_by_user_id or "").strip(),
        "notes": payload.notes,
        "handshake_state": "awaiting_target_consent",
        "source_handshake_at": _utcnow_iso(),
        "source_handshake_by": str(requested_by or "").strip() or "Unknown User",
        "source_handshake_user_id": str(requested_by_user_id or "").strip() or None,
        "target_handshake_at": None,
        "target_handshake_by": None,
        "target_handshake_user_id": None,
        "handshake_completed_at": None,
        "source_package_code": source_project.get("package_code"),
        "source_package_name": source_project.get("package_name"),
        "target_package_code": target_project.get("package_code"),
        "target_package_name": target_project.get("package_name"),
        "created_at": _utcnow_iso(),
        "updated_at": _utcnow_iso(),
    }

    result = _requests_collection().insert_one(data)
    data["_id"] = result.inserted_id
    try:
        create_audit_log(
            "link_request_created",
            str(requested_by_user_id or "").strip() or None,
            "link_request",
            str(result.inserted_id),
            {
                "source_project_id": source_project_id,
                "target_project_id": target_project_id,
                "handshake_state": "awaiting_target_consent",
            },
        )
    except Exception:
        pass
    return _enrich_request(data) or data


def get_link_request_by_id(request_id: str) -> dict | None:
    object_id = _to_object_id(request_id)
    if object_id is None:
        return None

    request = _requests_collection().find_one({"_id": object_id})
    return _enrich_request(request)


def _can_manage_request(
    request: dict[str, Any],
    user_id: str,
    *,
    user_email: str = "",
    side: str,
) -> bool:
    source_project_id = str(request.get("source_project_id") or "")
    target_project_id = str(request.get("target_project_id") or "")

    if side == "source":
        return user_can_access_project(source_project_id, user_id, user_email)
    if side == "target":
        return user_can_access_project(target_project_id, user_id, user_email)
    return user_can_access_project(source_project_id, user_id, user_email) or user_can_access_project(
        target_project_id,
        user_id,
        user_email,
    )


def _validate_active_handshake_keys(request: dict[str, Any]) -> None:
    source_project_id = _normalize_value(request.get("source_project_id"))
    target_project_id = _normalize_value(request.get("target_project_id"))
    source_key = _normalize_value(request.get("source_key"))
    target_key = _normalize_value(request.get("target_key"))
    source_key_hash = _normalize_value(request.get("source_key_hash"))
    target_key_hash = _normalize_value(request.get("target_key_hash"))

    active_source_key = get_active_key_doc_for_project(source_project_id)
    active_target_key = get_active_key_doc_for_project(target_project_id)

    active_source_hash = _normalize_value(active_source_key.get("key_hash")) if active_source_key else ""
    active_target_hash = _normalize_value(active_target_key.get("key_hash")) if active_target_key else ""

    source_matches_hash = bool(source_key_hash and active_source_hash and source_key_hash == active_source_hash)
    source_matches_legacy = bool(
        source_key and active_source_key and _normalize_value(active_source_key.get("key_value")) == source_key
    )
    if active_source_key is None or not (source_matches_hash or source_matches_legacy):
        raise ValueError(
            "The requesting workspace must still present the same active link key to complete the handshake."
        )

    target_matches_hash = bool(target_key_hash and active_target_hash and target_key_hash == active_target_hash)
    target_matches_legacy = bool(
        target_key and active_target_key and _normalize_value(active_target_key.get("key_value")) == target_key
    )
    if active_target_key is None or not (target_matches_hash or target_matches_legacy):
        raise ValueError(
            "The receiving workspace must still present the same active link key to complete the handshake."
        )


def approve_link_request(
    request_id: str,
    *,
    approved_by: str,
    approver_user_id: str,
    approver_user_email: str = "",
    approval_notes: str | None = None,
    is_admin: bool = False,
) -> dict | None:
    object_id = _to_object_id(request_id)
    if object_id is None:
        return None

    request = _requests_collection().find_one({"_id": object_id})
    if request is None:
        return None

    if not is_admin and not _can_manage_request(
        request,
        approver_user_id,
        user_email=approver_user_email,
        side="target",
    ):
        raise PermissionError("Not authorized to approve this link request.")

    if str(request.get("status") or "").strip().lower() == "approved":
        return _enrich_request(request)

    source_project_id = _normalize_value(request.get("source_project_id"))
    target_project_id = _normalize_value(request.get("target_project_id"))
    if not source_project_id or not target_project_id:
        raise ValueError("Link request project references are invalid.")
    if not project_supports_link_keys(source_project_id):
        raise ValueError("The requesting workspace no longer supports link capabilities.")
    if not project_supports_link_keys(target_project_id):
        raise ValueError("The receiving workspace no longer supports link capabilities.")

    _assert_household_branch_capacity(source_project_id, target_project_id)

    _validate_active_handshake_keys(request)

    now = _utcnow_iso()
    _requests_collection().update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": "approved",
                "handshake_state": "complete",
                "target_handshake_at": now,
                "target_handshake_by": approved_by,
                "target_handshake_user_id": approver_user_id,
                "handshake_completed_at": now,
                "approved_by": approved_by,
                "approved_at": now,
                "approval_notes": approval_notes,
                "updated_at": now,
            }
        },
    )

    source_household_id = str(request.get("source_household_id") or "").strip()
    target_household_id = str(request.get("target_household_id") or "").strip()

    if source_household_id and target_household_id:
        existing_link = _household_links_collection().find_one(
            {
                "$or": [
                    {
                        "source_household_id": source_household_id,
                        "target_household_id": target_household_id,
                    },
                    {
                        "source_household_id": target_household_id,
                        "target_household_id": source_household_id,
                    },
                ]
            }
        )

        if existing_link is None:
            _household_links_collection().insert_one(
                {
                    "source_household_id": source_household_id,
                    "target_household_id": target_household_id,
                    # This non-ancestry relationship marker is intentionally excluded from lineage traversal.
                    "relationship_type": LINKED_HOUSEHOLD_RELATIONSHIP_TYPE,
                    "link_status": "approved",
                    "linked_by_key": request.get("source_key"),
                    "source_key": request.get("source_key"),
                    "target_key": request.get("target_key"),
                    "created_at": now,
                    "updated_at": now,
                }
            )

    updated = _requests_collection().find_one({"_id": object_id})
    try:
        create_audit_log(
            "link_request_approved",
            str(approver_user_id or "").strip() or None,
            "link_request",
            str(object_id),
            {
                "source_project_id": _normalize_value(request.get("source_project_id")),
                "target_project_id": _normalize_value(request.get("target_project_id")),
                "handshake_state": "complete",
            },
        )
    except Exception:
        pass
    return _enrich_request(updated)


def reject_link_request(
    request_id: str,
    *,
    rejected_by: str,
    rejector_user_id: str,
    rejector_user_email: str = "",
    rejection_notes: str | None = None,
    is_admin: bool = False,
) -> dict | None:
    object_id = _to_object_id(request_id)
    if object_id is None:
        return None

    request = _requests_collection().find_one({"_id": object_id})
    if request is None:
        return None

    if not is_admin and not _can_manage_request(
        request,
        rejector_user_id,
        user_email=rejector_user_email,
        side="target",
    ):
        raise PermissionError("Not authorized to reject this link request.")

    current_status = str(request.get("status") or "").strip().lower()
    if current_status == "approved":
        raise ValueError("Approved links must be revoked, not rejected.")

    now = _utcnow_iso()
    _requests_collection().update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": "rejected",
                "handshake_state": "rejected",
                "rejected_by": rejected_by,
                "rejected_at": now,
                "rejection_notes": rejection_notes,
                "updated_at": now,
            }
        },
    )

    updated = _requests_collection().find_one({"_id": object_id})
    try:
        create_audit_log(
            "link_request_rejected",
            str(rejector_user_id or "").strip() or None,
            "link_request",
            str(object_id),
            {
                "source_project_id": _normalize_value(request.get("source_project_id")),
                "target_project_id": _normalize_value(request.get("target_project_id")),
            },
        )
    except Exception:
        pass
    return _enrich_request(updated)


def revoke_link_request(
    request_id: str,
    *,
    revoked_by: str,
    revoker_user_id: str,
    revoker_user_email: str = "",
    revoke_notes: str | None = None,
    is_admin: bool = False,
) -> dict | None:
    object_id = _to_object_id(request_id)
    if object_id is None:
        return None

    request = _requests_collection().find_one({"_id": object_id})
    if request is None:
        return None

    if not is_admin and not _can_manage_request(
        request,
        revoker_user_id,
        user_email=revoker_user_email,
        side="either",
    ):
        raise PermissionError("Not authorized to revoke this link request.")

    current_status = str(request.get("status") or "").strip().lower()
    if current_status not in {"pending", "approved"}:
        raise ValueError("Only pending or approved link requests can be revoked.")

    now = _utcnow_iso()
    _requests_collection().update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": "revoked",
                "handshake_state": "revoked",
                "revoked_by": revoked_by,
                "revoked_at": now,
                "revoke_notes": revoke_notes,
                "updated_at": now,
            }
        },
    )

    source_household_id = str(request.get("source_household_id") or "").strip()
    target_household_id = str(request.get("target_household_id") or "").strip()

    if source_household_id and target_household_id:
        _household_links_collection().delete_many(
            {
                "$or": [
                    {
                        "source_household_id": source_household_id,
                        "target_household_id": target_household_id,
                    },
                    {
                        "source_household_id": target_household_id,
                        "target_household_id": source_household_id,
                    },
                ]
            }
        )

    updated = _requests_collection().find_one({"_id": object_id})
    try:
        create_audit_log(
            "link_request_revoked",
            str(revoker_user_id or "").strip() or None,
            "link_request",
            str(object_id),
            {
                "source_project_id": _normalize_value(request.get("source_project_id")),
                "target_project_id": _normalize_value(request.get("target_project_id")),
            },
        )
    except Exception:
        pass
    return _enrich_request(updated)
