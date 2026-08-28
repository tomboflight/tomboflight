from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import hmac
import json
import secrets
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.config import settings
from app.database import get_database
from app.services.audit_log_service import write_audit_log
from app.services.email_service import (
    send_bridge_paint_invitation_email,
    send_bridge_paint_promotion_email,
)


COLLECTION = "bridge_event_invitations"
EVENT_CODE = "bridge_paint_2026"
LEGACY_EXPOSED_CODE_PREFIX = "BRIDGE-PAINT-"
PACKAGE_NAMES: dict[str, str] = {
    "legacy_snapshot": "Legacy Snapshot",
    "legacy_portrait_intro": "Legacy Portrait Intro",
    "digital_legacy_portrait": "Digital Legacy Portrait",
    "household_foundation": "Household Foundation",
    "heirloom_legacy_tree": "Heirloom Legacy Tree",
    "legacy_plus": "Legacy Plus",
    "family_estate_concierge": "Family Estate Concierge",
    "command_structure_network": "Command Structure Network",
}
PUBLIC_ACCESS_RESPONSE: dict[str, Any] = {
    "success": True,
    "message": (
        "If this invitation is valid and matches the invited email address, "
        "the private event offer will be sent to that mailbox."
    ),
}


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _normalize_email(value: Any) -> str:
    return _normalize(value).lower()


def _now() -> datetime:
    return datetime.now(UTC)


def _collection():
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")
    return db[COLLECTION]


def ensure_bridge_event_invite_indexes() -> None:
    collection = _collection()
    collection.create_index(
        [("token_hash", ASCENDING)],
        name="bridge_event_invite_token_hash_unique",
        unique=True,
        partialFilterExpression={"token_hash": {"$type": "string"}},
    )
    collection.create_index(
        [("active_key", ASCENDING)],
        name="bridge_event_invite_active_key_unique",
        unique=True,
        partialFilterExpression={"active_key": {"$type": "string"}},
    )
    collection.create_index(
        [("event_code", ASCENDING), ("email", ASCENDING), ("status", ASCENDING)],
        name="bridge_event_invite_recipient_status",
    )
    collection.create_index(
        [("event_code", ASCENDING), ("created_at", DESCENDING)],
        name="bridge_event_invite_created_desc",
    )


def _event_expiration() -> datetime:
    raw = _normalize(settings.bridge_paint_event_expires_at)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception as exc:
        raise RuntimeError("Private Bridge Event expiration is not configured correctly.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _promotion_codes() -> dict[str, str]:
    raw = _normalize(settings.bridge_paint_promotion_codes_json)
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except Exception as exc:
        raise RuntimeError("Private Bridge Event promotion configuration is invalid.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Private Bridge Event promotion configuration is invalid.")

    codes: dict[str, str] = {}
    for package_code in PACKAGE_NAMES:
        value = _normalize(payload.get(package_code))
        if not value:
            continue
        if value.upper().startswith(LEGACY_EXPOSED_CODE_PREFIX):
            raise RuntimeError(
                "Previously published Bridge Event promotion codes must be revoked and replaced."
            )
        codes[package_code] = value
    return codes


def bridge_paint_configuration_status() -> dict[str, Any]:
    try:
        configured_packages = sorted(_promotion_codes())
        expiration = _event_expiration()
        error = None
    except RuntimeError as exc:
        configured_packages = []
        expiration = None
        error = str(exc)
    return {
        "event_code": EVENT_CODE,
        "configured": len(configured_packages) == len(PACKAGE_NAMES) and error is None,
        "configured_packages": configured_packages,
        "required_packages": sorted(PACKAGE_NAMES),
        "expires_at": expiration.isoformat() if expiration else None,
        "configuration_error": error,
    }


def _token_hash(token: str) -> str:
    normalized = _normalize(token)
    key = _normalize(settings.secret_key).encode("utf-8")
    if not normalized or not key:
        return ""
    return hmac.new(key, normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def _active_key(email: str, package_code: str) -> str:
    payload = f"{EVENT_CODE}:{_normalize_email(email)}:{_normalize(package_code).lower()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _actor(current_user: dict[str, Any]) -> dict[str, str | None]:
    return {
        "user_id": _normalize(
            current_user.get("_id")
            or current_user.get("id")
            or current_user.get("user_id")
        )
        or None,
        "email": _normalize_email(current_user.get("email")) or None,
        "name": _normalize(current_user.get("full_name") or current_user.get("name"))
        or None,
    }


def _safe_audit(
    *,
    current_user: dict[str, Any] | None,
    action: str,
    target_id: str,
    email: str,
    package_code: str,
    result: str = "success",
) -> None:
    actor = _actor(current_user or {})
    try:
        write_audit_log(
            actor_user_id=actor["user_id"],
            actor_email=actor["email"],
            actor_name=actor["name"],
            action=action,
            target_type="bridge_event_invitation",
            target_id=target_id,
            after={
                "event_code": EVENT_CODE,
                "recipient_email": email,
                "package_code": package_code,
            },
            context={"surface": "secure_bridge_event_access"},
            result=result,
        )
    except Exception:
        # The invitation record retains audit_status=pending for operational
        # reconciliation if the shared audit collection is temporarily down.
        try:
            _collection().update_one(
                {"_id": ObjectId(target_id)},
                {"$set": {"audit_status": "pending", "updated_at": _now()}},
            )
        except Exception:
            pass


def _serialize_invitation(document: dict[str, Any]) -> dict[str, Any]:
    expires_at = document.get("expires_at")
    status = _normalize(document.get("status")) or "unknown"
    if isinstance(expires_at, datetime) and expires_at <= _now() and status == "delivered":
        status = "expired"
    return {
        "id": _normalize(document.get("_id")),
        "event_code": EVENT_CODE,
        "email": _normalize_email(document.get("email")),
        "package_code": _normalize(document.get("package_code")),
        "package_name": PACKAGE_NAMES.get(
            _normalize(document.get("package_code")),
            _normalize(document.get("package_code")),
        ),
        "status": status,
        "expires_at": expires_at.isoformat() if isinstance(expires_at, datetime) else _normalize(expires_at),
        "invitation_delivery_status": _normalize(
            document.get("invitation_delivery_status")
        )
        or None,
        "promotion_delivery_status": _normalize(
            document.get("promotion_delivery_status")
        )
        or None,
        "created_at": (
            document.get("created_at").isoformat()
            if isinstance(document.get("created_at"), datetime)
            else _normalize(document.get("created_at"))
        ),
        "fulfilled_at": (
            document.get("fulfilled_at").isoformat()
            if isinstance(document.get("fulfilled_at"), datetime)
            else _normalize(document.get("fulfilled_at")) or None
        ),
    }


def create_bridge_paint_invitation(
    *,
    current_user: dict[str, Any],
    email: str,
    package_code: str,
    reason: str,
) -> dict[str, Any]:
    normalized_email = _normalize_email(email)
    normalized_package = _normalize(package_code).lower()
    normalized_reason = _normalize(reason)
    if "@" not in normalized_email:
        raise ValueError("A valid invited email address is required.")
    if normalized_package not in PACKAGE_NAMES:
        raise ValueError("Select an eligible Tomb of Light package.")
    if len(normalized_reason) < 3:
        raise ValueError("An operational reason of at least 3 characters is required.")

    codes = _promotion_codes()
    if normalized_package not in codes:
        raise RuntimeError(
            "A rotated promotion code is not configured for the selected package."
        )
    expires_at = _event_expiration()
    if expires_at <= _now():
        raise RuntimeError("The private Bridge Event offer has expired.")

    collection = _collection()
    now = _now()
    active_key = _active_key(normalized_email, normalized_package)
    existing = collection.find_one({"active_key": active_key})
    if existing:
        existing_expiration = existing.get("expires_at")
        if isinstance(existing_expiration, datetime) and existing_expiration > now:
            result = _serialize_invitation(existing)
            result["invitation_created"] = False
            return result
        collection.update_one(
            {"_id": existing.get("_id"), "active_key": active_key},
            {
                "$set": {"status": "expired", "updated_at": now},
                "$unset": {"token_hash": "", "active_key": ""},
            },
        )
    collection.update_many(
        {
            "event_code": EVENT_CODE,
            "email": normalized_email,
            "package_code": normalized_package,
            "status": {"$in": ["pending", "delivered", "delivery_failed"]},
        },
        {
            "$set": {
                "status": "revoked",
                "revoked_reason": "superseded_by_new_invitation",
                "revoked_at": now,
                "updated_at": now,
            },
            "$unset": {"token_hash": "", "active_key": ""},
        },
    )

    access_token = "tolbe_" + secrets.token_urlsafe(32)
    document = {
        "event_code": EVENT_CODE,
        "email": normalized_email,
        "package_code": normalized_package,
        "active_key": active_key,
        "token_hash": _token_hash(access_token),
        "status": "pending",
        "reason": normalized_reason,
        "expires_at": expires_at,
        "created_at": now,
        "updated_at": now,
        "created_by_user_id": _actor(current_user)["user_id"],
        "created_by_email": _actor(current_user)["email"],
        "invitation_delivery_status": "pending",
        "promotion_delivery_status": "not_requested",
        "audit_status": "recorded",
    }
    try:
        inserted = collection.insert_one(document)
    except DuplicateKeyError:
        raced = collection.find_one({"active_key": active_key})
        if raced:
            result = _serialize_invitation(raced)
            result["invitation_created"] = False
            return result
        raise RuntimeError("The secure invitation could not be created safely.")
    invitation_id = str(inserted.inserted_id)
    delivery = send_bridge_paint_invitation_email(
        to_email=normalized_email,
        access_token=access_token,
        package_name=PACKAGE_NAMES[normalized_package],
        expires_at=expires_at.isoformat(),
    )
    if not bool(delivery.get("sent")):
        collection.update_one(
            {"_id": inserted.inserted_id},
            {
                "$set": {
                    "status": "delivery_failed",
                    "invitation_delivery_status": "failed",
                    "invitation_delivery_error": _normalize(delivery.get("error"))[:200],
                    "updated_at": _now(),
                },
                "$unset": {"token_hash": "", "active_key": ""},
            },
        )
        _safe_audit(
            current_user=current_user,
            action="bridge_event.invitation_delivery_failed",
            target_id=invitation_id,
            email=normalized_email,
            package_code=normalized_package,
            result="failed",
        )
        raise RuntimeError("The secure invitation email could not be delivered.")

    collection.update_one(
        {"_id": inserted.inserted_id},
        {
            "$set": {
                "status": "delivered",
                "invitation_delivery_status": "sent",
                "invitation_sent_at": _now(),
                "updated_at": _now(),
            }
        },
    )
    _safe_audit(
        current_user=current_user,
        action="bridge_event.invitation_sent",
        target_id=invitation_id,
        email=normalized_email,
        package_code=normalized_package,
    )
    refreshed = collection.find_one({"_id": inserted.inserted_id}) or {
        **document,
        "_id": inserted.inserted_id,
        "status": "delivered",
        "invitation_delivery_status": "sent",
    }
    result = _serialize_invitation(refreshed)
    result["invitation_created"] = True
    return result


def request_bridge_paint_access(*, email: str, access_token: str) -> dict[str, Any]:
    normalized_email = _normalize_email(email)
    token_hash = _token_hash(access_token)
    if "@" not in normalized_email or not token_hash:
        return dict(PUBLIC_ACCESS_RESPONSE)

    collection = _collection()
    invitation = collection.find_one(
        {
            "event_code": EVENT_CODE,
            "email": normalized_email,
            "token_hash": token_hash,
            "status": "delivered",
        }
    )
    if not invitation:
        return dict(PUBLIC_ACCESS_RESPONSE)
    expires_at = invitation.get("expires_at")
    if not isinstance(expires_at, datetime) or expires_at <= _now():
        collection.update_one(
            {"_id": invitation.get("_id"), "status": "delivered"},
            {
                "$set": {"status": "expired", "updated_at": _now()},
                "$unset": {"token_hash": "", "active_key": ""},
            },
        )
        return dict(PUBLIC_ACCESS_RESPONSE)

    locked = collection.find_one_and_update(
        {
            "_id": invitation.get("_id"),
            "token_hash": token_hash,
            "status": "delivered",
        },
        {
            "$set": {
                "status": "fulfillment_in_progress",
                "fulfillment_started_at": _now(),
                "updated_at": _now(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if not locked:
        return dict(PUBLIC_ACCESS_RESPONSE)

    package_code = _normalize(locked.get("package_code"))
    try:
        promotion_code = _promotion_codes().get(package_code, "")
    except RuntimeError:
        promotion_code = ""
    if not promotion_code:
        collection.update_one(
            {"_id": locked.get("_id"), "status": "fulfillment_in_progress"},
            {
                "$set": {
                    "status": "delivered",
                    "promotion_delivery_status": "configuration_blocked",
                    "updated_at": _now(),
                }
            },
        )
        return dict(PUBLIC_ACCESS_RESPONSE)

    delivery = send_bridge_paint_promotion_email(
        to_email=normalized_email,
        promotion_code=promotion_code,
        package_name=PACKAGE_NAMES.get(package_code, package_code),
        expires_at=expires_at.isoformat(),
    )
    invitation_id = _normalize(locked.get("_id"))
    if not bool(delivery.get("sent")):
        collection.update_one(
            {"_id": locked.get("_id"), "status": "fulfillment_in_progress"},
            {
                "$set": {
                    "status": "delivered",
                    "promotion_delivery_status": "failed",
                    "promotion_delivery_error": _normalize(delivery.get("error"))[:200],
                    "updated_at": _now(),
                }
            },
        )
        _safe_audit(
            current_user=None,
            action="bridge_event.promotion_delivery_failed",
            target_id=invitation_id,
            email=normalized_email,
            package_code=package_code,
            result="failed",
        )
        return dict(PUBLIC_ACCESS_RESPONSE)

    collection.update_one(
        {"_id": locked.get("_id"), "status": "fulfillment_in_progress"},
        {
            "$set": {
                "status": "fulfilled",
                "promotion_delivery_status": "sent",
                "fulfilled_at": _now(),
                "updated_at": _now(),
            },
            "$unset": {
                "token_hash": "",
                "active_key": "",
                "promotion_delivery_error": "",
            },
        },
    )
    _safe_audit(
        current_user=None,
        action="bridge_event.promotion_delivered",
        target_id=invitation_id,
        email=normalized_email,
        package_code=package_code,
    )
    return dict(PUBLIC_ACCESS_RESPONSE)


def list_bridge_paint_invitations(*, limit: int = 100) -> dict[str, Any]:
    collection = _collection()
    records = list(
        collection.find({"event_code": EVENT_CODE})
        .sort("created_at", DESCENDING)
        .limit(max(1, min(int(limit), 500)))
    )
    return {
        "configuration": bridge_paint_configuration_status(),
        "count": len(records),
        "items": [_serialize_invitation(record) for record in records],
    }


def revoke_bridge_paint_invitation(
    *,
    invitation_id: str,
    current_user: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    normalized_reason = _normalize(reason)
    if len(normalized_reason) < 3:
        raise ValueError("A revocation reason of at least 3 characters is required.")
    if not ObjectId.is_valid(invitation_id):
        raise ValueError("Invitation id is invalid.")
    collection = _collection()
    invitation = collection.find_one({"_id": ObjectId(invitation_id), "event_code": EVENT_CODE})
    if not invitation:
        raise ValueError("Invitation was not found.")
    if _normalize(invitation.get("status")) in {"fulfilled", "revoked", "expired"}:
        raise ValueError("This invitation can no longer be revoked.")

    collection.update_one(
        {"_id": invitation.get("_id")},
        {
            "$set": {
                "status": "revoked",
                "revoked_reason": normalized_reason,
                "revoked_at": _now(),
                "updated_at": _now(),
            },
            "$unset": {"token_hash": "", "active_key": ""},
        },
    )
    _safe_audit(
        current_user=current_user,
        action="bridge_event.invitation_revoked",
        target_id=invitation_id,
        email=_normalize_email(invitation.get("email")),
        package_code=_normalize(invitation.get("package_code")),
    )
    refreshed = collection.find_one({"_id": invitation.get("_id")}) or {
        **invitation,
        "status": "revoked",
    }
    return _serialize_invitation(refreshed)
