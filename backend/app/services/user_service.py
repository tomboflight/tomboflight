from datetime import UTC, datetime, timedelta
import hashlib
import re
import secrets
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.config import settings
from app.database import get_database
from app.schemas.user import UserCreate
from app.services.audit_log_service import write_audit_log
from app.services.email_service import (
    send_email_change_verification_email,
    send_email_changed_notice,
)


EMAIL_CHANGE_TTL_MINUTES = 30
_UNSET = object()


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_email(value: Any) -> str:
    return _normalize_text(value).lower()


def _user_query(user_id: str) -> dict[str, Any]:
    try:
        return {"_id": ObjectId(user_id)}
    except Exception:
        return {"_id": user_id}


def normalize_phone_number(value: str | None) -> str | None:
    raw = _normalize_text(value)
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if raw.startswith("+") and 8 <= len(digits) <= 15:
        return f"+{digits}"
    raise ValueError("Enter a valid phone number, including country code when outside the United States.")


def normalize_mailing_address(value: dict[str, Any] | None) -> dict[str, str] | None:
    if value is None:
        return None
    normalized = {
        "line1": _normalize_text(value.get("line1")),
        "line2": _normalize_text(value.get("line2")),
        "city": _normalize_text(value.get("city")),
        "region": _normalize_text(value.get("region")),
        "postal_code": _normalize_text(value.get("postal_code")),
        "country": (_normalize_text(value.get("country")) or "US").upper(),
    }
    if not any(normalized[key] for key in ("line1", "line2", "city", "region", "postal_code")):
        return None
    if not all(normalized[key] for key in ("line1", "city", "region", "postal_code")):
        raise ValueError("Street address, city, state or region, and postal code are required.")
    if len(normalized["country"]) != 2:
        raise ValueError("Country must use a two-letter country code.")
    return normalized


def format_mailing_address(address: dict[str, str] | None) -> str | None:
    if not address:
        return None
    street = ", ".join(part for part in (address.get("line1"), address.get("line2")) if part)
    locality = ", ".join(part for part in (address.get("city"), address.get("region")) if part)
    tail = " ".join(part for part in (locality, address.get("postal_code")) if part)
    return ", ".join(part for part in (street, tail, address.get("country")) if part)


def _email_change_url(token: str) -> str:
    source = (
        settings.password_reset_base_url_clean
        or settings.stripe_billing_portal_return_url_clean
        or "https://tomboflight.com"
    )
    parsed = urlsplit(source)
    base_url = urlunsplit(
        (
            parsed.scheme or "https",
            parsed.netloc or "tomboflight.com",
            "/billing.html",
            "",
            "",
        )
    )
    return f"{base_url}#mode=email-change&token={quote(token, safe='')}"


def _email_change_token_hash(token: str) -> str:
    return hashlib.sha256(_normalize_text(token).encode("utf-8")).hexdigest()


def list_users() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.users.find().sort("created_at", -1))


def create_user(payload: UserCreate) -> dict:
    db = get_database()
    data = payload.model_dump()
    data["role"] = "user"
    data["account_type"] = "customer"
    data["created_at"] = datetime.now(UTC).isoformat()
    data["full_name"] = f"{payload.first_name} {payload.last_name}".strip()
    data["status"] = "pending_activation"
    data["password_hash"] = None
    data["requires_account_activation"] = True
    data["last_login_at"] = None
    data["password_reset_requested_at"] = None
    data["password_reset_expires_at"] = None
    data["password_reset_token_hash"] = None
    data["password_reset_requested_via"] = None
    data["password_reset_requested_by"] = None
    data["password_reset_requested_by_user_id"] = None
    data["password_reset_used_at"] = None

    if db is None:
        data["_id"] = "local-user-preview"
        return data

    result = db.users.insert_one(data)
    data["_id"] = result.inserted_id
    return data



def update_user_profile(
    user_id: str,
    *,
    full_name: str,
    phone_number: str | None | object = _UNSET,
    mailing_address: dict[str, Any] | None | object = _UNSET,
) -> dict | None:
    db = get_database()
    if db is None:
        return None

    normalized_name = str(full_name or '').strip()
    if not normalized_name:
        raise ValueError('full_name is required.')

    query = _user_query(user_id)
    before = db.users.find_one(query)
    if before is None:
        return None

    phone_was_supplied = phone_number is not _UNSET
    address_was_supplied = mailing_address is not _UNSET
    normalized_phone = (
        normalize_phone_number(phone_number if isinstance(phone_number, str) else None)
        if phone_was_supplied
        else before.get("phone_number")
    )
    normalized_address = (
        normalize_mailing_address(mailing_address if isinstance(mailing_address, dict) else None)
        if address_was_supplied
        else before.get("mailing_address_structured")
    )
    now = datetime.now(UTC).isoformat()
    updates: dict[str, Any] = {
        'full_name': normalized_name,
        'phone_number': normalized_phone,
        'mailing_address': format_mailing_address(normalized_address),
        'mailing_address_structured': normalized_address,
        'updated_at': now,
        'billing_profile_sync_status': 'pending' if before.get('stripe_customer_id') else 'not_linked',
        'billing_profile_sync_requested_at': now,
    }

    db.users.update_one(
        query,
        {'$set': updates},
    )

    billing_sync_status = updates['billing_profile_sync_status']
    if before.get('stripe_customer_id'):
        try:
            from app.services.billing_service import sync_account_contact_to_stripe

            sync_account_contact_to_stripe(
                customer_id=_normalize_text(before.get('stripe_customer_id')),
                full_name=normalized_name,
                phone_number=normalized_phone,
                mailing_address=normalized_address,
                include_phone=phone_was_supplied,
                include_address=address_was_supplied,
            )
            billing_sync_status = 'synced'
        except Exception:
            billing_sync_status = 'pending'
        db.users.update_one(
            query,
            {'$set': {
                'billing_profile_sync_status': billing_sync_status,
                'billing_profile_synced_at': now if billing_sync_status == 'synced' else None,
            }},
        )

    after = db.users.find_one(query)
    try:
        write_audit_log(
            actor_user_id=user_id,
            actor_email=_normalize_email((after or {}).get('email')) or None,
            actor_name=normalized_name,
            action='customer_profile_updated',
            target_type='user',
            target_id=user_id,
            before={
                'full_name': before.get('full_name'),
                'phone_number': before.get('phone_number'),
                'mailing_address': before.get('mailing_address_structured') or before.get('mailing_address'),
            },
            after={
                'full_name': normalized_name,
                'phone_number': normalized_phone,
                'mailing_address': normalized_address,
                'billing_sync_status': billing_sync_status,
            },
            context={'source': 'customer_self_service'},
        )
    except Exception:
        pass
    return after


def request_email_change(user_id: str, *, new_email: str, current_password: str) -> dict[str, Any]:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")
    query = _user_query(user_id)
    user = db.users.find_one(query)
    if user is None:
        raise ValueError("User account not found.")

    normalized_email = _normalize_email(new_email)
    current_email = _normalize_email(user.get("email"))
    if normalized_email == current_email:
        raise ValueError("Enter a different email address.")
    duplicate = db.users.find_one({"email": normalized_email}, {"_id": 1})
    if duplicate is not None:
        raise ValueError("That email address is already connected to an account.")

    from app.services.auth_service import verify_password

    if not verify_password(current_password, _normalize_text(user.get("password_hash"))):
        raise ValueError("Current password is incorrect.")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(minutes=EMAIL_CHANGE_TTL_MINUTES)
    pending = {
        "pending_email": normalized_email,
        "pending_email_change_token_hash": _email_change_token_hash(token),
        "pending_email_change_requested_at": datetime.now(UTC).isoformat(),
        "pending_email_change_expires_at": expires_at.isoformat(),
    }
    db.users.update_one(query, {"$set": pending})
    delivery = send_email_change_verification_email(
        to_email=normalized_email,
        verification_url=_email_change_url(token),
        expires_at=expires_at.isoformat(),
    )
    if not bool(delivery.get("sent")):
        db.users.update_one(
            query,
            {"$unset": {key: "" for key in pending}},
        )
        raise RuntimeError("Verification email could not be delivered. Try again later.")

    try:
        write_audit_log(
            actor_user_id=user_id,
            actor_email=current_email or None,
            actor_name=_normalize_text(user.get("full_name")) or None,
            action="customer_email_change_requested",
            target_type="user",
            target_id=user_id,
            before={"email": current_email},
            after={"pending_email": normalized_email},
            context={"source": "customer_self_service", "delivery_sent": True},
        )
    except Exception:
        pass
    return {
        "success": True,
        "message": "Verification sent to the new email address.",
        "expires_at": expires_at.isoformat(),
    }


def confirm_email_change(token: str) -> dict[str, Any]:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")
    token_hash = _email_change_token_hash(token)
    allowed_status = {
        "$nin": ["deleted", "deletion_in_progress", "permanently_deleted"]
    }
    user = db.users.find_one(
        {
            "pending_email_change_token_hash": token_hash,
            "status": allowed_status,
        }
    )
    if user is None:
        raise ValueError("Email change link is invalid, expired, or already used.")
    expires_raw = _normalize_text(user.get("pending_email_change_expires_at"))
    try:
        expires_at = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
    except Exception as exc:
        raise ValueError("Email change link is invalid, expired, or already used.") from exc
    if expires_at < datetime.now(UTC):
        raise ValueError("Email change link is invalid, expired, or already used.")

    user_id = str(user.get("_id"))
    old_email = _normalize_email(user.get("email"))
    new_email = _normalize_email(user.get("pending_email"))
    if not new_email or db.users.find_one({"email": new_email, "_id": {"$ne": user.get("_id")}}, {"_id": 1}):
        raise ValueError("That email address is already connected to an account.")

    now = datetime.now(UTC).isoformat()
    try:
        result = db.users.update_one(
            {
                "_id": user.get("_id"),
                "pending_email_change_token_hash": token_hash,
                "pending_email": new_email,
                "status": allowed_status,
            },
            {
                "$set": {
                    "email": new_email,
                    "email_verified_at": now,
                    "email_updated_at": now,
                    "session_token_version": int(user.get("session_token_version") or 0) + 1,
                },
                "$addToSet": {"email_aliases": old_email},
                "$unset": {
                    "pending_email": "",
                    "pending_email_change_token_hash": "",
                    "pending_email_change_requested_at": "",
                    "pending_email_change_expires_at": "",
                },
            },
        )
    except DuplicateKeyError as exc:
        raise ValueError("That email address is already connected to an account.") from exc
    if int(getattr(result, "modified_count", 0)) != 1:
        raise ValueError("Email change link is invalid, expired, or already used.")

    stripe_customer_id = _normalize_text(user.get("stripe_customer_id"))
    if stripe_customer_id:
        try:
            from app.services.billing_service import sync_verified_email_to_stripe

            sync_verified_email_to_stripe(customer_id=stripe_customer_id, email=new_email)
        except Exception:
            db.users.update_one(
                {"_id": user.get("_id")},
                {
                    "$set": {
                        "billing_profile_sync_status": "pending",
                        "billing_profile_sync_requested_at": now,
                    }
                },
            )

    try:
        write_audit_log(
            actor_user_id=user_id,
            actor_email=new_email,
            actor_name=_normalize_text(user.get("full_name")) or None,
            action="customer_email_changed",
            target_type="user",
            target_id=user_id,
            before={"email": old_email},
            after={"email": new_email, "sessions_revoked": True},
            context={"source": "verified_customer_self_service"},
        )
    except Exception:
        pass
    try:
        send_email_changed_notice(to_email=old_email, new_email=new_email)
    except Exception:
        pass
    return {
        "success": True,
        "message": "Email updated. Sign in again with your new email address.",
    }
