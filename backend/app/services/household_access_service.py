from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId

from app.core.package_catalog import get_package, normalize_package_code
from app.core.role_catalog import normalize_project_member_role
from app.database import get_database
from app.services.audit_log_service import create_audit_log
from app.services.email_service import send_household_invite_email
from app.services.project_entitlement_service import get_project_entitlement
from app.services.project_membership_service import (
    ensure_project_owner_membership,
    get_project_access_snapshot,
)

MEMBERSHIP_COLLECTION = "project_members"
INVITES_COLLECTION = "household_invites"

ACTIVE_MEMBER_STATUSES = {"active"}
ACTIVE_INVITE_STATUSES = {"pending"}

ROLE_PRIORITY = {
    "billing_owner": 100,
    "co_owner": 80,
    "family_manager": 60,
    "contributor": 40,
    "viewer": 20,
    "minor_viewer": 10,
    "linked_relative": 10,
    "legacy_executor": 5,
}

ROLE_ASSIGNMENTS: dict[str, set[str]] = {
    "billing_owner": set(ROLE_PRIORITY.keys()),
    "co_owner": {"family_manager", "contributor", "viewer", "minor_viewer", "linked_relative"},
    "family_manager": {"contributor", "viewer", "minor_viewer"},
}

logger = logging.getLogger(__name__)

PRIVACY_SCOPES = {
    "private_to_owner",
    "private_to_owner_and_co_owner",
    "household_private",
    "household_shared",
    "read_only",
    "link_only",
    "branch_shared",
    "linked_family_shared",
    "public_memorial",
    "minor_protected",
}

PRIVACY_SCOPE_ALIASES = {
    "shared_household_access": "household_shared",
    "household_shared": "household_shared",
    "read_only": "read_only",
    "link_only_access": "link_only",
    "link_only": "link_only",
    "branch_shared": "household_shared",
    "linked_family_shared": "link_only",
    "public_memorial": "read_only",
}

RELATIONSHIP_SCOPE_ALIASES = {
    "spouse": "spouse",
    "parent": "parent",
    "child": "child",
    "sibling": "sibling",
    "household_member": "household_member",
    "guardian": "guardian",
    "relative": "relative",
    "other": "other",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _normalize_email(value: Any) -> str:
    return _normalize(value).lower()


def _normalize_relationship_scope(value: Any) -> str:
    normalized = _normalize(value).lower()
    return RELATIONSHIP_SCOPE_ALIASES.get(normalized, normalized or "household_member")


def _normalize_privacy_scope(value: Any) -> str:
    normalized = _normalize(value).lower()
    return PRIVACY_SCOPE_ALIASES.get(normalized, normalized or "household_private")


def _to_oid(value: Any) -> ObjectId | None:
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _db():
    return get_database()


def _projects():
    return _db()["projects"]


def _members():
    return _db()[MEMBERSHIP_COLLECTION]


def _invites():
    return _db()[INVITES_COLLECTION]


def _find_project(project_id: str) -> dict[str, Any] | None:
    oid = _to_oid(project_id)
    if oid is None:
        return None
    return _projects().find_one({"_id": oid})


def _role_rank(role: str) -> int:
    return int(ROLE_PRIORITY.get(normalize_project_member_role(role, default="viewer"), 0))


def _can_assign_role(actor_role: str, target_role: str) -> bool:
    actor = normalize_project_member_role(actor_role, default="viewer")
    target = normalize_project_member_role(target_role, default="viewer")
    return target in ROLE_ASSIGNMENTS.get(actor, set())


def _is_active_invite(invite: dict[str, Any]) -> bool:
    status = _normalize(invite.get("status") or "pending").lower()
    if status not in ACTIVE_INVITE_STATUSES:
        return False
    expires_at = invite.get("expires_at")
    if not expires_at:
        return True
    try:
        expiration = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
    except Exception:
        return True
    return expiration >= _now()


def _parse_dt(value: Any) -> datetime | None:
    normalized = _normalize(value)
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except Exception:
        return None


def _expire_invite_if_needed(invite: dict[str, Any]) -> dict[str, Any]:
    invite_id = invite.get("_id")
    if invite_id is None:
        return invite
    status = _normalize(invite.get("status") or "pending").lower()
    if status != "pending":
        return invite
    expires_at = _parse_dt(invite.get("expires_at"))
    if expires_at is None or expires_at >= _now():
        return invite
    now_iso = _now().isoformat()
    _invites().update_one(
        {"_id": invite_id},
        {"$set": {"status": "expired", "expired_at": now_iso, "updated_at": now_iso}},
    )
    return _invites().find_one({"_id": invite_id}) or {**invite, "status": "expired", "expired_at": now_iso}


def _persist_invite_email_delivery(
    *,
    invite_id: Any,
    invite_document: dict[str, Any],
    email_delivery: dict[str, Any],
) -> bool:
    """Persist invite email delivery status; returns False when persistence fails."""
    sent = bool(email_delivery.get("sent"))
    updates = {
        "email_delivery_status": "sent" if sent else "failed",
        "email_delivery_error": None if sent else (_normalize(email_delivery.get("error")) or "email delivery failed"),
        "updated_at": _now().isoformat(),
    }
    invite_document.update(updates)
    try:
        _invites().update_one({"_id": invite_id}, {"$set": updates})
        logger.info(
            "household_access_service.invite_email_delivery_persisted invite_id=%s status=%s",
            _normalize(invite_id),
            updates["email_delivery_status"],
        )
        return True
    except Exception as exc:
        logger.exception(
            "household_access_service.invite_email_delivery_persist_failed invite_id=%s status=%s error=%s",
            _normalize(invite_id),
            updates["email_delivery_status"],
            str(exc),
        )
        return False


def _resolve_actor_role(project: dict[str, Any], actor_user: dict[str, Any]) -> str:
    snapshot = get_project_access_snapshot(
        project,
        user_id=_normalize(actor_user.get("id") or actor_user.get("_id") or actor_user.get("user_id")),
        email=_normalize_email(actor_user.get("email")),
    )
    role = normalize_project_member_role(snapshot.get("member_role"), default="viewer")
    if snapshot.get("via") == "owner_fallback" or role == "billing_owner":
        return "billing_owner"
    return role


def _resolve_member_seat_cap(project_id: str) -> int:
    entitlement = get_project_entitlement(project_id) or {}
    package_code = normalize_package_code(entitlement.get("package_code"))
    package = get_package(package_code) or {}
    package_lane = _normalize(entitlement.get("package_lane") or package.get("package_lane") or "household").lower()
    try:
        package_defined_members = int(package.get("max_members") or 0)
    except (TypeError, ValueError):
        package_defined_members = 0
    if package_defined_members > 0:
        included = package_defined_members
    else:
        included = {"portrait": 2, "household": 6, "network": 20, "organization": 25}.get(package_lane, 6)
    active_addons = list(entitlement.get("active_addons") or [])
    addon_seats = 0
    for addon in active_addons:
        addon_text = _normalize(addon).lower()
        if addon_text.startswith("extra_seat_"):
            try:
                addon_seats += int(addon_text.rsplit("_", 1)[-1])
            except Exception:
                addon_seats += 0
        elif addon_text in {"extra_seat", "extra_seat_pack"}:
            addon_seats += 1
    return included + addon_seats


def _active_member_count(project_id: str) -> int:
    return int(
        _members().count_documents(
            {"project_id": _normalize(project_id), "status": {"$in": sorted(ACTIVE_MEMBER_STATUSES)}}
        )
    )


def ensure_owner_membership(project_id: str) -> None:
    project = _find_project(project_id)
    if project is None:
        return
    ensure_project_owner_membership(project)


def list_project_members(project_id: str) -> list[dict[str, Any]]:
    ensure_owner_membership(project_id)
    cursor = _members().find({"project_id": _normalize(project_id)}).sort("created_at", 1)
    return list(cursor)


def list_project_invites(project_id: str) -> list[dict[str, Any]]:
    cursor = _invites().find({"project_id": _normalize(project_id)}).sort("created_at", -1)
    invites = list(cursor)
    return [_expire_invite_if_needed(invite) for invite in invites]


def create_household_invite(
    *,
    project_id: str,
    actor_user: dict[str, Any],
    email: str,
    member_role: str,
    relationship_scope: str,
    privacy_scope: str,
    notes: str = "",
    expires_in_days: int = 7,
    max_uses: int = 1,
) -> dict[str, Any]:
    logger.info(
        "household_access_service.create_household_invite.start context=%s",
        {
            "project_id": _normalize(project_id),
            "actor_user_id": _normalize(
                actor_user.get("id") or actor_user.get("_id") or actor_user.get("user_id")
            ),
            "actor_email": _normalize_email(actor_user.get("email")),
            "member_role": _normalize(member_role),
            "relationship_scope": _normalize(relationship_scope),
            "privacy_scope": _normalize(privacy_scope),
        },
    )
    project = _find_project(project_id)
    if project is None:
        logger.warning(
            "household_access_service.create_household_invite.project_not_found project_id=%s",
            _normalize(project_id),
        )
        raise ValueError("Workspace project not found.")

    actor_user_id = _normalize(actor_user.get("id") or actor_user.get("_id") or actor_user.get("user_id"))
    actor_role = _resolve_actor_role(project, actor_user)
    if actor_role not in ROLE_ASSIGNMENTS:
        logger.warning(
            "household_access_service.create_household_invite.forbidden actor_role=%s project_id=%s",
            actor_role,
            _normalize(project_id),
        )
        raise PermissionError("You do not have permission to invite household members.")

    normalized_role = normalize_project_member_role(member_role, default="viewer")
    if not _can_assign_role(actor_role, normalized_role):
        logger.warning(
            (
                "household_access_service.create_household_invite.role_assignment_forbidden "
                "actor_role=%s requested_role=%s project_id=%s"
            ),
            actor_role,
            normalized_role,
            _normalize(project_id),
        )
        raise PermissionError("Your role cannot assign the requested membership role.")

    normalized_email = _normalize_email(email)
    if not normalized_email:
        logger.warning(
            "household_access_service.create_household_invite.missing_email project_id=%s actor_user_id=%s",
            _normalize(project_id),
            actor_user_id,
        )
        raise ValueError("Invite email is required.")

    normalized_privacy_scope = _normalize_privacy_scope(privacy_scope or "household_private")
    if normalized_privacy_scope not in PRIVACY_SCOPES:
        logger.warning(
            (
                "household_access_service.create_household_invite.invalid_privacy_scope "
                "privacy_scope=%s normalized_privacy_scope=%s project_id=%s"
            ),
            _normalize(privacy_scope),
            normalized_privacy_scope,
            _normalize(project_id),
        )
        raise ValueError("Invalid privacy scope for invite.")

    active_member_count = _active_member_count(project_id)
    member_seat_cap = _resolve_member_seat_cap(project_id)
    logger.info(
        (
            "household_access_service.create_household_invite.capacity_check "
            "project_id=%s active_member_count=%s member_seat_cap=%s"
        ),
        _normalize(project_id),
        active_member_count,
        member_seat_cap,
    )
    if active_member_count >= member_seat_cap:
        raise ValueError("This workspace has reached the included seat limit for the active package.")

    existing_member = _members().find_one(
        {
            "project_id": _normalize(project_id),
            "email": normalized_email,
            "status": {"$in": sorted(ACTIVE_MEMBER_STATUSES)},
        }
    )
    if existing_member is not None:
        logger.warning(
            (
                "household_access_service.create_household_invite.member_already_active "
                "project_id=%s invite_email=%s existing_member_id=%s"
            ),
            _normalize(project_id),
            normalized_email,
            _normalize(existing_member.get("_id")),
        )
        raise ValueError("This email already has active workspace access.")

    now = _now()
    invite_key = f"hhinv_{secrets.token_urlsafe(24)}"
    document = {
        "project_id": _normalize(project_id),
        "email": normalized_email,
        "invite_key": invite_key,
        "key_type": "household_invite_key",
        "status": "pending",
        "member_role": normalized_role,
        "relationship_scope": _normalize_relationship_scope(relationship_scope or "household_member"),
        "privacy_scope": normalized_privacy_scope,
        "issuer_user_id": actor_user_id or None,
        "target_email": normalized_email,
        "allowed_role": normalized_role,
        "max_uses": max(1, int(max_uses or 1)),
        "use_count": 0,
        "notes": _normalize(notes),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "expires_at": (now + timedelta(days=max(1, int(expires_in_days or 7)))).isoformat(),
        "accepted_at": None,
        "revoked_at": None,
    }
    try:
        result = _invites().insert_one(document)
    except Exception as exc:
        logger.exception(
            "household_access_service.create_household_invite.insert_failed project_id=%s invite_email=%s error=%s",
            _normalize(project_id),
            normalized_email,
            str(exc),
        )
        raise
    document["_id"] = result.inserted_id
    logger.info(
        (
            "household_access_service.create_household_invite.inserted "
            "project_id=%s invite_id=%s invite_email=%s member_role=%s relationship_scope=%s privacy_scope=%s"
        ),
        _normalize(project_id),
        _normalize(result.inserted_id),
        normalized_email,
        normalized_role,
        _normalize_relationship_scope(relationship_scope or "household_member"),
        normalized_privacy_scope,
    )
    create_audit_log(
        "household_invite_created",
        actor_user_id or None,
        "household_invite",
        str(result.inserted_id),
        {
            "project_id": _normalize(project_id),
            "invite_email": normalized_email,
            "member_role": normalized_role,
        },
    )
    email_delivery: dict[str, Any] = {"sent": True}
    logger.info(
        "household_access_service.create_household_invite.email_attempt project_id=%s invite_id=%s invite_email=%s",
        _normalize(project_id),
        _normalize(result.inserted_id),
        normalized_email,
    )
    try:
        email_delivery = send_household_invite_email(
            to_email=normalized_email,
            invite_key=invite_key,
            project_id=_normalize(project_id),
            member_role=normalized_role,
            inviter_email=_normalize_email(actor_user.get("email")),
            is_resend=False,
        ) or {"sent": False, "error": "unknown_email_delivery_failure"}
    except Exception as exc:
        logger.exception(
            "household_access_service.create_household_invite.email_exception "
            "project_id=%s invite_id=%s invite_email=%s error=%s",
            _normalize(project_id),
            _normalize(result.inserted_id),
            normalized_email,
            str(exc),
        )
        email_delivery = {
            "sent": False,
            "error": str(exc) or type(exc).__name__,
            "exception_type": type(exc).__name__,
        }

    logger.info(
        "household_access_service.create_household_invite.email_result project_id=%s invite_id=%s sent=%s error=%s",
        _normalize(project_id),
        _normalize(result.inserted_id),
        bool(email_delivery.get("sent")),
        _normalize(email_delivery.get("error")),
    )
    _persist_invite_email_delivery(
        invite_id=result.inserted_id,
        invite_document=document,
        email_delivery=email_delivery,
    )
    return document


def accept_household_invite(*, invite_key: str, user: dict[str, Any]) -> dict[str, Any]:
    normalized_key = _normalize(invite_key)
    if not normalized_key:
        raise ValueError("Invite key is required.")

    invite = _invites().find_one({"invite_key": normalized_key})
    if invite is None:
        raise ValueError("Invite key was not found.")
    invite = _expire_invite_if_needed(invite)
    if not _is_active_invite(invite):
        raise ValueError("Invite is no longer active.")

    user_email = _normalize_email(user.get("email"))
    if user_email and _normalize_email(invite.get("email")) and user_email != _normalize_email(invite.get("email")):
        raise PermissionError("This invite was issued for a different email address.")

    project_id = _normalize(invite.get("project_id"))
    if _active_member_count(project_id) >= _resolve_member_seat_cap(project_id):
        raise ValueError("This workspace has reached the included seat limit for the active package.")

    user_id = _normalize(user.get("id") or user.get("_id") or user.get("user_id"))
    now = _now().isoformat()
    member_doc = {
        "project_id": project_id,
        "user_id": user_id or None,
        "email": user_email or _normalize_email(invite.get("email")) or None,
        "member_role": normalize_project_member_role(invite.get("member_role"), default="viewer"),
        "relationship_scope": _normalize_relationship_scope(invite.get("relationship_scope") or "household_member"),
        "privacy_scope": _normalize_privacy_scope(invite.get("privacy_scope") or "household_private"),
        "status": "active",
        "invited_by_user_id": _normalize(invite.get("issuer_user_id")) or None,
        "joined_at": now,
        "updated_at": now,
    }
    _members().update_one(
        {
            "project_id": project_id,
            "$or": [
                {"user_id": user_id},
                {"email": user_email or _normalize_email(invite.get("email"))},
            ],
        },
        {"$set": member_doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )

    if user_id:
        user_lookup: dict[str, Any] = {"$or": [{"id": user_id}, {"user_id": user_id}]}
        user_oid = _to_oid(user_id)
        if user_oid is not None:
            user_lookup["$or"] = [{"_id": user_oid}, *user_lookup["$or"]]
        _db()["users"].update_one(
            user_lookup,
            {
                "$set": {
                    "active_project_id": project_id,
                    "active_project_selected_at": now,
                }
            },
        )

    use_count = int(invite.get("use_count") or 0) + 1
    max_uses = max(1, int(invite.get("max_uses") or 1))
    invite_status = "accepted" if use_count >= max_uses else "pending"
    _invites().update_one(
        {"_id": invite["_id"]},
        {
            "$set": {
                "status": invite_status,
                "use_count": use_count,
                "accepted_at": now,
                "updated_at": now,
            }
        },
    )
    create_audit_log(
        "household_invite_accepted",
        user_id or None,
        "household_invite",
        str(invite["_id"]),
        {"project_id": project_id, "member_role": member_doc["member_role"]},
    )
    return (
        _members().find_one(
            {
                "project_id": project_id,
                "$or": [{"user_id": user_id}, {"email": user_email}],
            }
        )
        or member_doc
    )


def revoke_household_invite(*, invite_id: str, actor_user: dict[str, Any]) -> dict[str, Any] | None:
    oid = _to_oid(invite_id)
    if oid is None:
        return None
    invite = _invites().find_one({"_id": oid})
    if invite is None:
        return None
    invite = _expire_invite_if_needed(invite)
    project = _find_project(_normalize(invite.get("project_id")))
    if project is None:
        return None
    actor_role = _resolve_actor_role(project, actor_user)
    if actor_role not in {"billing_owner", "co_owner", "family_manager"}:
        raise PermissionError("You do not have permission to revoke invites.")
    now = _now().isoformat()
    _invites().update_one({"_id": oid}, {"$set": {"status": "revoked", "revoked_at": now, "updated_at": now}})
    actor_user_id = _normalize(actor_user.get("id") or actor_user.get("_id") or actor_user.get("user_id"))
    create_audit_log(
        "household_invite_revoked",
        actor_user_id or None,
        "household_invite",
        str(oid),
        {"project_id": _normalize(invite.get("project_id"))},
    )
    return _invites().find_one({"_id": oid})


def resend_household_invite(
    *,
    invite_id: str,
    actor_user: dict[str, Any],
    expires_in_days: int = 7,
) -> dict[str, Any] | None:
    oid = _to_oid(invite_id)
    if oid is None:
        return None
    invite = _invites().find_one({"_id": oid})
    if invite is None:
        return None
    invite = _expire_invite_if_needed(invite)
    project = _find_project(_normalize(invite.get("project_id")))
    if project is None:
        return None
    actor_role = _resolve_actor_role(project, actor_user)
    if actor_role not in {"billing_owner", "co_owner", "family_manager"}:
        raise PermissionError("You do not have permission to resend invites.")
    status_value = _normalize(invite.get("status") or "pending").lower()
    if status_value in {"accepted", "revoked"}:
        raise ValueError("Only pending or expired invites can be resent.")

    now = _now()
    new_key = f"hhinv_{secrets.token_urlsafe(24)}"
    updates = {
        "status": "pending",
        "invite_key": new_key,
        "use_count": 0,
        "accepted_at": None,
        "revoked_at": None,
        "expired_at": None,
        "updated_at": now.isoformat(),
        "expires_at": (now + timedelta(days=max(1, int(expires_in_days or 7)))).isoformat(),
    }
    _invites().update_one({"_id": oid}, {"$set": updates})
    actor_user_id = _normalize(actor_user.get("id") or actor_user.get("_id") or actor_user.get("user_id"))
    create_audit_log(
        "household_invite_resent",
        actor_user_id or None,
        "household_invite",
        str(oid),
        {"project_id": _normalize(invite.get("project_id")), "invite_email": _normalize_email(invite.get("email"))},
    )
    invite = _invites().find_one({"_id": oid})
    if invite is None:
        return None
    email_delivery: dict[str, Any] = {"sent": True}
    try:
        email_delivery = send_household_invite_email(
            to_email=_normalize_email(invite.get("email")),
            invite_key=new_key,
            project_id=_normalize(invite.get("project_id")),
            member_role=normalize_project_member_role(invite.get("member_role"), default="viewer"),
            inviter_email=_normalize_email(actor_user.get("email")),
            is_resend=True,
        ) or {"sent": False, "error": "unknown_email_delivery_failure"}
    except Exception as exc:
        logger.exception(
            "household_access_service.resend_household_invite.email_exception "
            "project_id=%s invite_id=%s invite_email=%s error=%s",
            _normalize(invite.get("project_id")),
            _normalize(oid),
            _normalize_email(invite.get("email")),
            str(exc),
        )
        email_delivery = {
            "sent": False,
            "error": str(exc) or type(exc).__name__,
            "exception_type": type(exc).__name__,
        }
    _persist_invite_email_delivery(
        invite_id=oid,
        invite_document=invite,
        email_delivery=email_delivery,
    )
    return invite


def delete_household_invite(*, invite_id: str, actor_user: dict[str, Any]) -> bool:
    oid = _to_oid(invite_id)
    if oid is None:
        return False
    invite = _invites().find_one({"_id": oid})
    if invite is None:
        return False
    invite = _expire_invite_if_needed(invite)
    project = _find_project(_normalize(invite.get("project_id")))
    if project is None:
        return False
    actor_role = _resolve_actor_role(project, actor_user)
    if actor_role not in {"billing_owner", "co_owner", "family_manager"}:
        raise PermissionError("You do not have permission to delete invites.")
    invite_status = _normalize(invite.get("status") or "pending").lower()

    delete_result = _invites().delete_one({"_id": oid})
    if int(getattr(delete_result, "deleted_count", 0)) <= 0:
        return False

    actor_user_id = _normalize(actor_user.get("id") or actor_user.get("_id") or actor_user.get("user_id"))
    create_audit_log(
        "household_invite_deleted",
        actor_user_id or None,
        "household_invite",
        str(oid),
        {
            "project_id": _normalize(invite.get("project_id")),
            "invite_status": invite_status,
        },
    )
    return True


def update_member_role(
    *,
    project_id: str,
    membership_id: str,
    member_role: str,
    actor_user: dict[str, Any],
) -> dict[str, Any] | None:
    oid = _to_oid(membership_id)
    if oid is None:
        return None
    membership = _members().find_one({"_id": oid, "project_id": _normalize(project_id)})
    if membership is None:
        return None
    project = _find_project(project_id)
    if project is None:
        return None
    actor_role = _resolve_actor_role(project, actor_user)
    actor_user_id = _normalize(actor_user.get("id") or actor_user.get("_id") or actor_user.get("user_id"))
    actor_email = _normalize_email(actor_user.get("email"))
    current_role = normalize_project_member_role(membership.get("member_role"), default="viewer")
    next_role = normalize_project_member_role(member_role, default="viewer")

    if current_role == "billing_owner" and next_role != "billing_owner":
        raise PermissionError(
            "Use billing owner transfer to pass ownership before changing the current billing owner role."
        )

    if next_role == "billing_owner":
        if actor_role != "billing_owner":
            raise PermissionError("Only the current billing owner can transfer billing owner access.")
        target_status = _normalize(membership.get("status") or "active").lower()
        if target_status not in ACTIVE_MEMBER_STATUSES:
            raise ValueError("Only active members can receive billing owner access.")
        if current_role == "billing_owner":
            return membership

        now = _now().isoformat()
        project_doc_id = project.get("_id")
        if project_doc_id is not None:
            _projects().update_one(
                {"_id": project_doc_id},
                {
                    "$set": {
                        "owner_user_id": _normalize(membership.get("user_id")) or None,
                        "owner_email": _normalize_email(membership.get("email")) or None,
                        "updated_at": now,
                    }
                },
            )

        _members().update_many(
            {
                "project_id": _normalize(project_id),
                "member_role": "billing_owner",
                "status": {"$in": sorted(ACTIVE_MEMBER_STATUSES)},
                "_id": {"$ne": oid},
            },
            {"$set": {"member_role": "co_owner", "updated_at": now}},
        )
        _members().update_one({"_id": oid}, {"$set": {"member_role": "billing_owner", "updated_at": now}})
        create_audit_log(
            "household_billing_owner_transferred",
            actor_user_id or None,
            "project_member",
            membership_id,
            {
                "project_id": _normalize(project_id),
                "previous_owner_user_id": _normalize(project.get("owner_user_id")) or None,
                "previous_owner_email": _normalize_email(project.get("owner_email")) or None,
                "next_owner_user_id": _normalize(membership.get("user_id")) or None,
                "next_owner_email": _normalize_email(membership.get("email")) or None,
                "requested_by_email": actor_email or None,
            },
        )
        return _members().find_one({"_id": oid})

    if not _can_assign_role(actor_role, next_role):
        raise PermissionError("You do not have permission to assign this role.")
    if _role_rank(next_role) >= _role_rank(actor_role):
        raise PermissionError("You can only assign roles below your own role level.")
    now = _now().isoformat()
    _members().update_one({"_id": oid}, {"$set": {"member_role": next_role, "updated_at": now}})
    create_audit_log(
        "household_role_changed",
        actor_user_id or None,
        "project_member",
        membership_id,
        {
            "project_id": _normalize(project_id),
            "previous_role": normalize_project_member_role(membership.get("member_role"), default="viewer"),
            "next_role": next_role,
        },
    )
    return _members().find_one({"_id": oid})


def revoke_membership(*, project_id: str, membership_id: str, actor_user: dict[str, Any]) -> dict[str, Any] | None:
    oid = _to_oid(membership_id)
    if oid is None:
        return None
    membership = _members().find_one({"_id": oid, "project_id": _normalize(project_id)})
    if membership is None:
        return None
    project = _find_project(project_id)
    if project is None:
        return None
    actor_role = _resolve_actor_role(project, actor_user)
    target_role = normalize_project_member_role(membership.get("member_role"), default="viewer")
    if actor_role not in ROLE_ASSIGNMENTS:
        raise PermissionError("You do not have permission to revoke memberships.")
    if target_role == "billing_owner":
        raise PermissionError("Billing owner access cannot be revoked from this action.")
    if _role_rank(target_role) >= _role_rank(actor_role):
        raise PermissionError("You can only revoke access for roles below your role level.")
    now = _now().isoformat()
    _members().update_one({"_id": oid}, {"$set": {"status": "revoked", "updated_at": now}})
    actor_user_id = _normalize(actor_user.get("id") or actor_user.get("_id") or actor_user.get("user_id"))
    create_audit_log(
        "household_membership_revoked",
        actor_user_id or None,
        "project_member",
        membership_id,
        {"project_id": _normalize(project_id), "target_role": target_role},
    )
    return _members().find_one({"_id": oid})


def list_my_memberships(user: dict[str, Any]) -> list[dict[str, Any]]:
    user_id = _normalize(user.get("id") or user.get("_id") or user.get("user_id"))
    email = _normalize_email(user.get("email"))
    filters: list[dict[str, Any]] = []
    if user_id:
        filters.append({"user_id": user_id})
    if email:
        filters.append({"email": email})
    if not filters:
        return []
    query = {"$or": filters}
    return list(_members().find(query).sort("updated_at", -1))
