import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from bson import ObjectId

from app.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_database
from app.schemas.auth import UserCreate
from app.services.audit_log_service import create_audit_log

PUBLIC_SIGNUP_ROLE = "user"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _current_user_id_from_doc(user: dict) -> str:
    raw_value = user.get("_id") or user.get("id") or user.get("user_id")
    return _normalize_text(raw_value)


def _password_reset_expiry_iso() -> str:
    expire_at = _now() + timedelta(
        minutes=max(5, int(settings.password_reset_token_expire_minutes or 30))
    )
    return expire_at.isoformat()


def _hash_password_reset_token(token: str) -> str:
    payload = f"{settings.secret_key}:{_normalize_text(token)}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _build_password_reset_url(token: str, email: str) -> str:
    base_url = (
        settings.password_reset_base_url_clean
        or "https://tomboflight.com/account-security.html"
    )
    encoded_token = quote(_normalize_text(token), safe="")
    encoded_email = quote(_normalize_text(email).lower(), safe="")
    joiner = "&" if "?" in base_url else "?"
    return f"{base_url}{joiner}mode=reset&token={encoded_token}&email={encoded_email}"


def _should_expose_password_reset_preview() -> bool:
    if bool(settings.password_reset_preview_enabled):
        return True

    return _normalize_text(settings.environment).lower() in {
        "development",
        "dev",
        "local",
        "test",
    }


def _clear_password_reset_fields() -> dict[str, object]:
    return {
        "password_reset_token_hash": None,
        "password_reset_expires_at": None,
        "password_reset_requested_at": None,
        "password_reset_requested_via": None,
        "password_reset_requested_by": None,
        "password_reset_requested_by_user_id": None,
    }


def build_user_response(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user.get("role", "user"),
        "status": user.get("status", "active"),
        "created_at": user["created_at"],
        "access_tier": user.get("access_tier"),
        "department_role": user.get("department_role"),
        "policy_version": user.get("policy_version"),
        "terms_accepted_at": user.get("terms_accepted_at"),
        "privacy_accepted_at": user.get("privacy_accepted_at"),
        "eligibility_attested_at": user.get("eligibility_attested_at"),
    }


def register_user(payload: UserCreate) -> dict | None:
    if not payload.terms_accepted:
        raise ValueError("You must accept the Terms of Service.")
    if not payload.privacy_accepted:
        raise ValueError("You must accept the Privacy Policy.")
    if not payload.eligibility_attested:
        raise ValueError(
            "You must confirm your eligibility and authority to create the account."
        )

    db = get_database()
    now_iso = _now_iso()

    if db is None:
        return {
            "_id": "local-user-preview",
            "email": payload.email.lower(),
            "full_name": payload.full_name.strip(),
            "role": PUBLIC_SIGNUP_ROLE,
            "status": "active",
            "created_at": now_iso,
            "policy_version": payload.policy_version,
            "terms_accepted_at": now_iso,
            "privacy_accepted_at": now_iso,
            "eligibility_attested_at": now_iso,
        }

    normalized_email = payload.email.lower()
    existing = db.users.find_one({"email": normalized_email})
    if existing is not None:
        if (
            not existing.get("password_hash")
            and str(existing.get("status") or "").strip().lower()
            in {"pending_activation", "checkout_pending_activation"}
        ):
            update_fields = {
                "full_name": payload.full_name.strip(),
                "role": existing.get("role") or PUBLIC_SIGNUP_ROLE,
                "status": "active",
                "password_hash": hash_password(payload.password),
                "password_updated_at": now_iso,
                "activated_at": now_iso,
                "requires_account_activation": False,
                "policy_version": payload.policy_version,
                "terms_accepted_at": now_iso,
                "privacy_accepted_at": now_iso,
                "eligibility_attested_at": now_iso,
                **_clear_password_reset_fields(),
            }
            db.users.update_one({"_id": existing["_id"]}, {"$set": update_fields})
            existing.update(update_fields)
            return existing

        return None

    user = {
        "email": normalized_email,
        "full_name": payload.full_name.strip(),
        "role": PUBLIC_SIGNUP_ROLE,
        "status": "active",
        "password_hash": hash_password(payload.password),
        "password_updated_at": now_iso,
        "created_at": now_iso,
        "last_login_at": None,
        **_clear_password_reset_fields(),
        "password_reset_used_at": None,
        "policy_version": payload.policy_version,
        "terms_accepted_at": now_iso,
        "privacy_accepted_at": now_iso,
        "eligibility_attested_at": now_iso,
    }

    result = db.users.insert_one(user)
    user["_id"] = result.inserted_id
    return user


def create_pending_checkout_user(
    email: str,
    *,
    full_name: str | None = None,
) -> dict | None:
    normalized_email = _normalize_text(email).lower()
    if not normalized_email:
        return None

    db = get_database()
    if db is None:
        return None

    existing = db.users.find_one({"email": normalized_email})
    if existing is not None:
        return existing

    now_iso = _now_iso()
    display_name = _normalize_text(full_name) or normalized_email.split("@")[0]
    user = {
        "email": normalized_email,
        "full_name": display_name,
        "role": PUBLIC_SIGNUP_ROLE,
        "status": "pending_activation",
        "password_hash": None,
        "password_updated_at": None,
        "created_at": now_iso,
        "created_from": "stripe_checkout",
        "requires_account_activation": True,
        "last_login_at": None,
        **_clear_password_reset_fields(),
        "password_reset_used_at": None,
        "policy_version": None,
        "terms_accepted_at": None,
        "privacy_accepted_at": None,
        "eligibility_attested_at": None,
    }

    result = db.users.insert_one(user)
    user["_id"] = result.inserted_id
    return user


def authenticate_user(email: str, password: str) -> str | None:
    db = get_database()
    if db is None:
        return create_access_token({"sub": email.lower(), "role": "user"})

    user = db.users.find_one({"email": email.lower()})
    if user is None:
        return None

    if user.get("status") != "active":
        return None

    password_hash = user.get("password_hash")
    if not password_hash or not verify_password(password, password_hash):
        return None

    now_iso = _now_iso()
    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "last_login_at": now_iso,
                **_clear_password_reset_fields(),
            }
        },
    )

    return create_access_token(
        {
            "sub": user["email"],
            "role": user.get("role", "user"),
            "user_id": str(user["_id"]),
        }
    )


def get_user_by_email(email: str) -> dict | None:
    db = get_database()
    if db is None:
        return None

    return db.users.find_one({"email": email.lower()})


def get_user_by_id(user_id: str) -> dict | None:
    db = get_database()
    if db is None:
        return None

    try:
        object_id = ObjectId(user_id)
    except Exception:
        return None

    return db.users.find_one({"_id": object_id})


def request_password_reset(
    email: str,
    *,
    requested_via: str = "self_service",
    requested_by_user_id: str | None = None,
    requested_by: str | None = None,
    expose_token: bool = False,
) -> dict[str, object]:
    normalized_email = _normalize_text(email).lower()
    generic_message = (
        "If this account exists, Tomb of Light created a secure password reset request."
    )
    generic_response: dict[str, object] = {
        "success": True,
        "message": generic_message,
        "delivery_mode": "admin_assisted",
    }

    db = get_database()
    if db is None:
        return generic_response

    user = db.users.find_one({"email": normalized_email})
    if user is None:
        return generic_response

    now_iso = _now_iso()
    expires_at = _password_reset_expiry_iso()
    token = secrets.token_urlsafe(32)
    token_hash = _hash_password_reset_token(token)

    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_reset_token_hash": token_hash,
                "password_reset_expires_at": expires_at,
                "password_reset_requested_at": now_iso,
                "password_reset_requested_via": _normalize_text(requested_via)
                or "self_service",
                "password_reset_requested_by": _normalize_text(requested_by) or None,
                "password_reset_requested_by_user_id": _normalize_text(
                    requested_by_user_id
                )
                or None,
                "password_reset_used_at": None,
            }
        },
    )

    try:
        create_audit_log(
            "password_reset_requested",
            requested_by_user_id or _current_user_id_from_doc(user) or None,
            "user",
            _current_user_id_from_doc(user),
            {
                "email": normalized_email,
                "requested_via": _normalize_text(requested_via) or "self_service",
                "admin_assisted": bool(expose_token),
            },
        )
    except Exception:
        pass

    should_expose = bool(expose_token) or _should_expose_password_reset_preview()
    if should_expose:
        generic_response["reset_token"] = token
        generic_response["reset_url"] = _build_password_reset_url(token, normalized_email)
        generic_response["expires_at"] = expires_at

    return generic_response


def reset_password_with_token(token: str, new_password: str) -> dict[str, object]:
    normalized_token = _normalize_text(token)
    if not normalized_token:
        raise ValueError("Password reset token is required.")

    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")

    token_hash = _hash_password_reset_token(normalized_token)
    user = db.users.find_one({"password_reset_token_hash": token_hash})
    if user is None:
        raise ValueError("Password reset token is invalid or expired.")

    expires_at = _normalize_text(user.get("password_reset_expires_at"))
    if not expires_at:
        raise ValueError("Password reset token is invalid or expired.")

    try:
        expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except Exception as exc:
        raise ValueError("Password reset token is invalid or expired.") from exc

    if expires_dt < _now():
        raise ValueError("Password reset token is invalid or expired.")

    if _normalize_text(user.get("status")).lower() not in {"", "active"}:
        raise ValueError("This account is not active.")

    now_iso = _now_iso()
    update_fields = {
        "password_hash": hash_password(new_password),
        "password_updated_at": now_iso,
        "password_reset_used_at": now_iso,
        **_clear_password_reset_fields(),
    }
    db.users.update_one({"_id": user["_id"]}, {"$set": update_fields})

    try:
        create_audit_log(
            "password_reset_completed",
            _current_user_id_from_doc(user) or None,
            "user",
            _current_user_id_from_doc(user),
            {
                "email": _normalize_text(user.get("email")).lower(),
            },
        )
    except Exception:
        pass

    return {
        "success": True,
        "message": "Password reset completed successfully.",
    }


def change_password(
    user_id: str,
    *,
    current_password: str,
    new_password: str,
) -> dict[str, object]:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")

    user = get_user_by_id(user_id)
    if user is None:
        raise ValueError("User account not found.")

    password_hash = _normalize_text(user.get("password_hash"))
    if not verify_password(current_password, password_hash):
        raise ValueError("Current password is incorrect.")

    now_iso = _now_iso()
    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_hash": hash_password(new_password),
                "password_updated_at": now_iso,
                **_clear_password_reset_fields(),
            }
        },
    )

    try:
        create_audit_log(
            "password_changed",
            user_id,
            "user",
            user_id,
            {"email": _normalize_text(user.get("email")).lower()},
        )
    except Exception:
        pass

    return {
        "success": True,
        "message": "Password updated successfully.",
    }


def admin_issue_password_reset(
    user_id: str,
    *,
    admin_user_id: str,
    admin_display: str,
) -> dict[str, object]:
    user = get_user_by_id(user_id)
    if user is None:
        raise ValueError("User account not found.")

    response = request_password_reset(
        _normalize_text(user.get("email")).lower(),
        requested_via="admin_assist",
        requested_by_user_id=admin_user_id,
        requested_by=admin_display,
        expose_token=True,
    )
    response["message"] = "Admin password reset issued successfully."
    return response
