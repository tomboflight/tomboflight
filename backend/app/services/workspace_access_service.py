from __future__ import annotations

from typing import Any, Iterable

from bson import ObjectId
from fastapi import HTTPException, status

from app.core.package_mapping import resolve_package_identity
from app.core.package_type_catalog import normalize_package_type
from app.core.role_catalog import normalize_project_member_role
from app.database import get_database
from app.services.audit_log_service import create_audit_log
from app.services.entitlement_service import resolve_project_entitlements
from app.services.project_member_service import is_project_member
from app.services.project_membership_service import get_project_access_snapshot

PAID_PACKAGE_STATUSES = {
    "paid",
    "complete",
    "completed",
    "succeeded",
}
WORKSPACE_ADMIN_ROLE_KEYS = {
    "admin",
    "super_admin",
    "root_admin",
    "platform_admin",
    "operations_admin",
    "executive_technology",
    "operations",
}


def _normalize_value(value: Any) -> str:
    return str(value or "").strip()


def _normalize_email(value: Any) -> str:
    return _normalize_value(value).lower()


def _current_user_id(user: dict[str, Any]) -> str:
    return _normalize_value(user.get("id") or user.get("_id") or user.get("user_id"))


def _current_user_email(user: dict[str, Any]) -> str:
    return _normalize_email(user.get("email"))


def _current_user_name(user: dict[str, Any]) -> str:
    return _normalize_value(user.get("full_name") or user.get("name"))


def _has_workspace_admin_access(user: dict[str, Any]) -> bool:
    role_values = {
        _normalize_value(user.get("role")).lower(),
        _normalize_value(user.get("access_tier")).lower(),
        _normalize_value(user.get("department_role")).lower(),
    }
    return any(value in WORKSPACE_ADMIN_ROLE_KEYS for value in role_values if value)


def _to_object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _project_id_candidates(project_id: str) -> list[Any]:
    values: list[Any] = [str(project_id)]
    oid = _to_object_id(project_id)
    if oid is not None:
        values.append(oid)
    return values


def _family_is_visible_to_user(
    family: dict[str, Any],
    *,
    current_user_id: str,
    current_user_email: str,
    current_user_name: str,
) -> bool:
    owner_user_id = _normalize_value(family.get("owner_user_id"))
    owner_email = _normalize_email(family.get("owner_email"))

    shared_with_user_ids = [
        _normalize_value(value)
        for value in (family.get("shared_with_user_ids") or [])
        if value is not None
    ]
    shared_with_emails = [
        _normalize_email(value)
        for value in (family.get("shared_with_emails") or [])
        if value is not None
    ]

    if owner_user_id and owner_user_id == current_user_id:
        return True

    if owner_email and owner_email == current_user_email:
        return True

    if current_user_id in shared_with_user_ids:
        return True

    if current_user_email in shared_with_emails:
        return True

    if not owner_user_id and not owner_email:
        created_by = _normalize_value(family.get("created_by"))
        if created_by and (
            created_by == current_user_name or created_by.lower() == current_user_email
        ):
            return True

    return False


def family_is_visible_to_user(
    family: dict[str, Any],
    *,
    current_user_id: str,
    current_user_email: str,
    current_user_name: str,
) -> bool:
    return _family_is_visible_to_user(
        family,
        current_user_id=current_user_id,
        current_user_email=current_user_email,
        current_user_name=current_user_name,
    )


def _require_database():
    db = get_database()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database is not connected.",
        )
    return db


def _find_project_by_id(project_id: str) -> dict[str, Any] | None:
    oid = _to_object_id(project_id)
    if oid is None:
        return None
    return _require_database()["projects"].find_one({"_id": oid})


def _find_family_by_id(family_id: str) -> dict[str, Any] | None:
    oid = _to_object_id(family_id)
    if oid is None:
        return None
    return _require_database()["families"].find_one({"_id": oid})


def _find_member_by_id(member_id: str) -> dict[str, Any] | None:
    oid = _to_object_id(member_id)
    if oid is None:
        return None
    return _require_database()["family_members"].find_one({"_id": oid})


def _find_project_for_family(family: dict[str, Any] | None) -> dict[str, Any] | None:
    if not family:
        return None

    db = _require_database()
    project_id = _normalize_value(family.get("project_id"))
    if project_id:
        project = _find_project_by_id(project_id)
        if project is not None:
            return project

    family_id = _normalize_value(family.get("_id") or family.get("id"))
    if family_id:
        project = db["projects"].find_one(
            {"family_id": family_id},
            sort=[("updated_at", -1), ("created_at", -1)],
        )
        if project is not None:
            return project

    intake_submission_id = _normalize_value(family.get("intake_submission_id"))
    if intake_submission_id:
        project = db["projects"].find_one(
            {"intake_submission_id": intake_submission_id},
            sort=[("updated_at", -1), ("created_at", -1)],
        )
        if project is not None:
            return project

    return None


def _find_family_for_project(project: dict[str, Any] | None) -> dict[str, Any] | None:
    if not project:
        return None

    db = _require_database()
    family_id = _normalize_value(project.get("family_id"))
    if family_id:
        family = _find_family_by_id(family_id)
        if family is not None:
            return family

    project_id = _normalize_value(project.get("_id") or project.get("id"))
    if project_id:
        family = db["families"].find_one(
            {"project_id": project_id},
            sort=[("updated_at", -1), ("created_at", -1)],
        )
        if family is not None:
            return family

    intake_submission_id = _normalize_value(project.get("intake_submission_id"))
    if intake_submission_id:
        family = db["families"].find_one(
            {"intake_submission_id": intake_submission_id},
            sort=[("updated_at", -1), ("created_at", -1)],
        )
        if family is not None:
            return family

    return None


def _is_paid_package_order(order: dict[str, Any] | None) -> bool:
    if not isinstance(order, dict):
        return False

    item_type = _normalize_value(order.get("item_type") or "package").lower()
    status_value = _normalize_value(order.get("status")).lower()

    return item_type == "package" and status_value in PAID_PACKAGE_STATUSES


def _get_paid_package_order_for_project(project_id: str) -> dict[str, Any] | None:
    db = _require_database()
    cursor = db["orders"].find(
        {"project_id": {"$in": _project_id_candidates(project_id)}}
    ).sort("created_at", -1)

    for order in cursor:
        if _is_paid_package_order(order):
            return order

    return None


def _get_active_project_entitlement(project_id: str) -> dict[str, Any] | None:
    db = _require_database()
    entitlements = db["project_entitlements"]
    return entitlements.find_one({"project_id": str(project_id), "status": "active"})


def _audit_entitlement_drift(
    project_id: str,
    reason: str,
    *,
    entitlement: dict[str, Any] | None = None,
    paid_order: dict[str, Any] | None = None,
) -> None:
    try:
        create_audit_log(
            "strict_entitlement_access_drift",
            None,
            "project",
            str(project_id),
            {
                "reason": reason,
                "entitlement_package_code": _normalize_value(
                    (entitlement or {}).get("package_code")
                ),
                "entitlement_package_lane": _normalize_value(
                    (entitlement or {}).get("package_lane")
                ),
                "paid_order_package_code": _normalize_value(
                    (paid_order or {}).get("package_code")
                ),
                "paid_order_package_slug": _normalize_value(
                    (paid_order or {}).get("package_slug")
                ),
                "paid_order_package_lane": _normalize_value(
                    (paid_order or {}).get("package_lane")
                ),
                "paid_order_id": _normalize_value((paid_order or {}).get("_id")),
            },
        )
    except Exception:
        pass


def _normalize_lane_value(value: Any) -> str:
    return normalize_package_type(_normalize_value(value), default="")


def resolve_strict_paid_active_project_entitlement(project_id: str) -> dict[str, Any]:
    normalized_project_id = _normalize_value(project_id)
    if not normalized_project_id:
        raise PermissionError("Workspace project id is required.")

    entitlement_doc = _get_active_project_entitlement(normalized_project_id)
    if entitlement_doc is None:
        _audit_entitlement_drift(normalized_project_id, "missing_active_entitlement")
        raise PermissionError("Active workspace entitlement is required.")

    paid_order = _get_paid_package_order_for_project(normalized_project_id)
    if paid_order is None:
        _audit_entitlement_drift(
            normalized_project_id,
            "missing_paid_order",
            entitlement=entitlement_doc,
        )
        raise PermissionError("A paid package order is required for this workspace.")

    entitlement_identity = resolve_package_identity(entitlement_doc.get("package_code"))
    paid_order_identity = resolve_package_identity(
        paid_order.get("package_code") or paid_order.get("package_slug")
    )

    entitlement_package_code = _normalize_value(
        entitlement_identity.get("package_code") or entitlement_doc.get("package_code")
    )
    paid_order_package_code = _normalize_value(
        paid_order_identity.get("package_code")
        or paid_order.get("package_code")
        or paid_order.get("package_slug")
    )

    if not entitlement_package_code or not paid_order_package_code:
        _audit_entitlement_drift(
            normalized_project_id,
            "unresolved_package_identity",
            entitlement=entitlement_doc,
            paid_order=paid_order,
        )
        raise PermissionError("Workspace package identity could not be verified.")

    if entitlement_package_code != paid_order_package_code:
        _audit_entitlement_drift(
            normalized_project_id,
            "package_code_mismatch",
            entitlement=entitlement_doc,
            paid_order=paid_order,
        )
        raise PermissionError("Workspace entitlement does not match paid package order.")

    entitlement_lane = _normalize_lane_value(
        entitlement_doc.get("package_lane") or entitlement_identity.get("package_lane")
    )
    paid_order_lane = _normalize_lane_value(
        paid_order.get("package_lane")
        or paid_order.get("project_lane")
        or paid_order_identity.get("package_lane")
    )
    if not entitlement_lane or not paid_order_lane:
        _audit_entitlement_drift(
            normalized_project_id,
            "missing_package_lane",
            entitlement=entitlement_doc,
            paid_order=paid_order,
        )
        raise PermissionError("Workspace package lane could not be verified.")
    if entitlement_lane != paid_order_lane:
        _audit_entitlement_drift(
            normalized_project_id,
            "package_lane_mismatch",
            entitlement=entitlement_doc,
            paid_order=paid_order,
        )
        raise PermissionError("Workspace package lane does not match paid package order.")

    active_addons = list(entitlement_doc.get("active_addons") or [])
    try:
        resolved_entitlements = resolve_project_entitlements(
            entitlement_package_code,
            active_addons,
        )
    except Exception:
        _audit_entitlement_drift(
            normalized_project_id,
            "entitlement_resolution_failed",
            entitlement=entitlement_doc,
            paid_order=paid_order,
        )
        raise PermissionError("Workspace entitlement could not be resolved.")

    return {
        "package_code": entitlement_package_code,
        "active_addons": active_addons,
        "resolved_entitlements": resolved_entitlements,
        "entitlement": entitlement_doc,
        "paid_order": paid_order,
    }


def _resolve_project_entitlement_map(project: dict[str, Any]) -> dict[str, Any]:
    project_id = _normalize_value(project.get("_id") or project.get("id"))
    try:
        return resolve_strict_paid_active_project_entitlement(project_id)
    except PermissionError:
        return {
            "package_code": "",
            "active_addons": [],
            "resolved_entitlements": {},
            "entitlement": _get_active_project_entitlement(project_id),
            "paid_order": _get_paid_package_order_for_project(project_id),
        }


def _project_is_visible_to_user(
    project: dict[str, Any],
    family: dict[str, Any] | None,
    current_user: dict[str, Any],
) -> bool:
    if _has_workspace_admin_access(current_user):
        return True

    current_user_id = _current_user_id(current_user)
    current_user_email = _current_user_email(current_user)
    current_user_name = _current_user_name(current_user)
    access_snapshot = get_project_access_snapshot(
        project,
        user_id=current_user_id,
        email=current_user_email,
    )

    if access_snapshot.get("accessible"):
        return True

    owner_user_ids = {
        _normalize_value(project.get("owner_user_id")),
        _normalize_value((family or {}).get("owner_user_id")),
    }
    owner_emails = {
        _normalize_email(project.get("owner_email")),
        _normalize_email((family or {}).get("owner_email")),
    }

    if current_user_id and current_user_id in owner_user_ids:
        return True

    if current_user_email and current_user_email in owner_emails:
        return True

    project_id = _normalize_value(project.get("_id") or project.get("id"))
    if project_id and is_project_member(project_id, current_user_id, current_user_email):
        return True

    if family is not None and not any(value for value in owner_user_ids | owner_emails):
        return family_is_visible_to_user(
            family,
            current_user_id=current_user_id,
            current_user_email=current_user_email,
            current_user_name=current_user_name,
        )

    return False


def resolve_workspace_context(
    current_user: dict[str, Any],
    *,
    project_id: str = "",
    family_id: str = "",
    member_id: str = "",
) -> dict[str, Any]:
    normalized_project_id = _normalize_value(project_id)
    normalized_family_id = _normalize_value(family_id)
    normalized_member_id = _normalize_value(member_id)

    member = None
    if normalized_member_id:
        if not ObjectId.is_valid(normalized_member_id):
            raise HTTPException(status_code=400, detail="Invalid member id.")
        member = _find_member_by_id(normalized_member_id)
        if member is None:
            raise HTTPException(status_code=404, detail="Family member not found.")
        if not normalized_family_id:
            normalized_family_id = _normalize_value(member.get("family_id"))

    family = None
    if normalized_family_id:
        if not ObjectId.is_valid(normalized_family_id):
            raise HTTPException(status_code=400, detail="Invalid family id.")
        family = _find_family_by_id(normalized_family_id)
        if family is None:
            raise HTTPException(status_code=404, detail="Family not found.")

    project = None
    if normalized_project_id:
        if not ObjectId.is_valid(normalized_project_id):
            raise HTTPException(status_code=400, detail="Invalid project id.")
        project = _find_project_by_id(normalized_project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")

    if project is None and family is not None:
        project = _find_project_for_family(family)

    if family is None and project is not None:
        family = _find_family_for_project(project)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace project could not be resolved.",
        )

    if family is not None:
        family_doc_id = _normalize_value(family.get("_id") or family.get("id"))
        family_project_id = _normalize_value(family.get("project_id"))
        project_doc_id = _normalize_value(project.get("_id") or project.get("id"))
        project_family_id = _normalize_value(project.get("family_id"))

        if family_project_id and family_project_id != project_doc_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Family does not belong to the requested workspace.",
            )

        if project_family_id and family_doc_id and project_family_id != family_doc_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Requested family does not match the current workspace.",
            )

        if member is not None and _normalize_value(member.get("family_id")) != family_doc_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Family member does not belong to the requested family.",
            )

    if not _project_is_visible_to_user(project, family, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this workspace.",
        )

    access_snapshot = get_project_access_snapshot(
        project,
        user_id=_current_user_id(current_user),
        email=_current_user_email(current_user),
    )
    membership = (access_snapshot or {}).get("membership") or {}

    entitlement_map = _resolve_project_entitlement_map(project)
    return {
        "project": project,
        "family": family,
        "member": member,
        "package_code": entitlement_map.get("package_code"),
        "active_addons": entitlement_map.get("active_addons") or [],
        "resolved_entitlements": entitlement_map.get("resolved_entitlements") or {},
        "entitlement": entitlement_map.get("entitlement"),
        "paid_order": entitlement_map.get("paid_order"),
        "access_snapshot": access_snapshot,
        "member_role": _normalize_value(access_snapshot.get("member_role") or "viewer") or "viewer",
        "relationship_scope": _normalize_value(membership.get("relationship_scope") or "household_member")
        or "household_member",
        "member_privacy_scope": _normalize_value(membership.get("privacy_scope") or "household_private")
        or "household_private",
        "link_status": _normalize_value(membership.get("link_status") or "active") or "active",
        "is_admin": _has_workspace_admin_access(current_user),
    }


def require_workspace_capability(
    current_user: dict[str, Any],
    *,
    project_id: str = "",
    family_id: str = "",
    member_id: str = "",
    capabilities: Iterable[str],
    detail: str,
) -> dict[str, Any]:
    context = resolve_workspace_context(
        current_user,
        project_id=project_id,
        family_id=family_id,
        member_id=member_id,
    )

    if context.get("is_admin"):
        return context

    resolved_entitlements = context.get("resolved_entitlements") or {}
    normalized_capabilities = [
        _normalize_value(capability).lower()
        for capability in capabilities
        if _normalize_value(capability)
    ]

    if not any(bool(resolved_entitlements.get(capability)) for capability in normalized_capabilities):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )

    return context


def require_workspace_member_role(
    context: dict[str, Any],
    *,
    allowed_roles: Iterable[str],
    detail: str,
) -> dict[str, Any]:
    if context.get("is_admin"):
        return context

    normalized_role = normalize_project_member_role(
        context.get("member_role"),
        default="viewer",
    )
    allowed = {
        normalize_project_member_role(role, default="viewer")
        for role in allowed_roles
        if _normalize_value(role)
    }
    if normalized_role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )
    return context


def list_accessible_families_for_user(
    current_user: dict[str, Any],
    *,
    capabilities: Iterable[str] = (),
) -> list[dict[str, Any]]:
    db = _require_database()
    if _has_workspace_admin_access(current_user):
        return list(db["families"].find().sort("created_at", -1))

    normalized_capabilities = [
        _normalize_value(capability).lower()
        for capability in capabilities
        if _normalize_value(capability)
    ]

    families: list[dict[str, Any]] = []
    cursor = db["families"].find().sort("created_at", -1)
    for family in cursor:
        family_id = _normalize_value(family.get("_id"))
        try:
            context = resolve_workspace_context(current_user, family_id=family_id)
        except HTTPException:
            continue

        if normalized_capabilities:
            resolved_entitlements = context.get("resolved_entitlements") or {}
            if not any(
                bool(resolved_entitlements.get(capability))
                for capability in normalized_capabilities
            ):
                continue

        families.append(family)

    return families


def count_workspace_uploads(
    *,
    family_id: str = "",
    project_id: str = "",
) -> int:
    db = _require_database()
    if project_id:
        return int(db["uploaded_files"].count_documents({"project_id": project_id}))
    if family_id:
        return int(db["uploaded_files"].count_documents({"family_id": family_id}))
    return 0
