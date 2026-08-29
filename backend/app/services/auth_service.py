import base64
import binascii
import hashlib
import hmac
import secrets
import struct
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from bson import ObjectId
from cryptography.fernet import Fernet, InvalidToken
from pymongo import ASCENDING

from app.config import settings
from app.core.admin_permission_registry import (
    is_canonical_ceo_email,
    requires_privileged_mfa as _requires_privileged_mfa,
)
from app.core.password_policy import validate_password_strength
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.database import get_database
from app.schemas.auth import UserCreate
from app.services.audit_log_service import create_audit_log
from app.services.email_service import (
    send_account_activation_email,
    send_password_changed_email,
    send_password_reset_email,
)

PUBLIC_SIGNUP_ROLE = "user"


def ensure_auth_indexes() -> None:
    """Fail closed on ambiguous email identities or duplicate live tokens."""
    users = get_database()["users"]
    users.create_index(
        [("email", ASCENDING)],
        name="idx_users_email_unique",
        unique=True,
    )
    users.create_index(
        [("account_activation_token_hash", ASCENDING)],
        name="idx_users_activation_token_hash_unique",
        unique=True,
        partialFilterExpression={
            "account_activation_token_hash": {"$type": "string"}
        },
    )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _get_database_or_none():
    try:
        return get_database()
    except RuntimeError:
        return None


def _current_user_id_from_doc(user: dict) -> str:
    raw_value = user.get("_id") or user.get("id") or user.get("user_id")
    return _normalize_text(raw_value)


def _password_reset_expiry_iso() -> str:
    expire_at = _now() + timedelta(
        minutes=max(5, int(settings.password_reset_token_expire_minutes or 30))
    )
    return expire_at.isoformat()


def _account_activation_expiry_iso() -> str:
    expire_at = _now() + timedelta(
        hours=max(1, int(settings.account_activation_token_expire_hours or 24))
    )
    return expire_at.isoformat()


def _hash_password_reset_token(token: str) -> str:
    payload = f"{settings.secret_key}:{_normalize_text(token)}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _hash_account_activation_token(token: str) -> str:
    payload = f"{settings.secret_key}:account-activation:{_normalize_text(token)}".encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()


def _hash_recovery_code(code: str, *, user_id: str) -> str:
    payload = (
        f"{settings.secret_key}:mfa-recovery:{_normalize_text(user_id)}:{_normalize_text(code).lower()}"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _session_version(user: dict) -> int:
    try:
        return max(0, int(user.get("session_token_version") or 0))
    except Exception:
        return 0


def has_privileged_admin_authority(user: dict[str, Any] | None) -> bool:
    """Resolve privileged authority from the identity and active role grants."""
    if not user:
        return False
    if _requires_privileged_mfa(user):
        return True

    user_id = _current_user_id_from_doc(user)
    if not user_id:
        return False
    user_id_candidates: list[Any] = [user_id]
    if ObjectId.is_valid(user_id):
        user_id_candidates.append(ObjectId(user_id))

    try:
        assignments = get_database()["user_role_assignments"].find(
            {"user_id": {"$in": user_id_candidates}}
        )
        assigned_role_codes = [
            assignment.get("role_code")
            for assignment in assignments
            if _normalize_text(assignment.get("status")).lower()
            in {"", "active", "enabled"}
        ]
    except Exception:
        # Do not manufacture privileged authority when its assignment source
        # cannot be resolved. Downstream admin permission resolution also
        # remains unavailable/fail-closed in this state.
        return False
    if not assigned_role_codes:
        return False
    enriched_user = dict(user)
    existing_role_codes = user.get("role_codes")
    if not isinstance(existing_role_codes, (list, tuple, set, frozenset)):
        existing_role_codes = [existing_role_codes] if existing_role_codes else []
    enriched_user["role_codes"] = [
        *existing_role_codes,
        *assigned_role_codes,
    ]
    return _requires_privileged_mfa(enriched_user)


def _assert_mfa_token_version(
    payload: dict[str, Any],
    user: dict[str, Any],
    *,
    token_label: str,
) -> None:
    try:
        token_version = int(payload.get("tv"))
    except (TypeError, ValueError):
        raise ValueError(f"Invalid {token_label}.") from None
    if token_version != _session_version(user):
        raise ValueError(f"Invalid {token_label}.")


def _mfa_encrypt_secret(secret: str, *, user_id: str) -> str:
    key_material = hashlib.sha256(
        f"{settings.secret_key}:mfa:{_normalize_text(user_id)}".encode("utf-8")
    ).digest()
    fernet_key = base64.urlsafe_b64encode(key_material)
    encrypted = Fernet(fernet_key).encrypt(_normalize_text(secret).encode("utf-8"))
    return encrypted.decode("utf-8")


def _mfa_decrypt_secret(secret_ciphertext: str, *, user_id: str) -> str:
    try:
        key_material = hashlib.sha256(
            f"{settings.secret_key}:mfa:{_normalize_text(user_id)}".encode("utf-8")
        ).digest()
        fernet_key = base64.urlsafe_b64encode(key_material)
        plaintext = Fernet(fernet_key).decrypt(
            _normalize_text(secret_ciphertext).encode("utf-8")
        )
        return plaintext.decode("utf-8", errors="ignore").strip()
    except (InvalidToken, ValueError, TypeError):
        return ""


def _generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("utf-8").rstrip("=")


def _totp_code(secret: str, *, timestamp: int) -> str:
    normalized = _normalize_text(secret).replace(" ", "").upper()
    if not normalized:
        return ""
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    try:
        key = base64.b32decode(normalized + padding, casefold=True)
    except binascii.Error:
        return ""
    timestep = int(timestamp // 30)
    digest = hmac.new(key, struct.pack(">Q", timestep), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1000000
    return f"{code:06d}"


def _verify_totp(secret: str, code: str) -> bool:
    normalized_code = _normalize_text(code)
    if not normalized_code.isdigit():
        return False
    now = int(_now().timestamp())
    window = max(0, int(settings.mfa_totp_window or 1))
    for delta in range(-window, window + 1):
        if hmac.compare_digest(_totp_code(secret, timestamp=now + (delta * 30)), normalized_code):
            return True
    return False


def _build_mfa_otpauth_uri(secret: str, *, email: str) -> str:
    issuer = _normalize_text(settings.mfa_totp_issuer) or "Tomb of Light"
    account = _normalize_text(email).lower()
    return f"otpauth://totp/{quote(issuer)}:{quote(account)}?secret={secret}&issuer={quote(issuer)}"


def _build_access_token_for_user(user: dict) -> str:
    return create_access_token(
        {
            "sub": user["email"],
            "role": user.get("role", "user"),
            "user_id": str(user["_id"]),
            "tv": _session_version(user),
            "mfa": bool(user.get("mfa_enabled")),
        }
    )


def _build_password_reset_url(token: str) -> str:
    base_url = (
        settings.password_reset_base_url_clean
        or "https://tomboflight.com/account-security.html"
    )
    parsed = urlsplit(base_url)
    base_without_fragment = urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.query, "")
    )
    encoded_token = quote(_normalize_text(token), safe="")
    # Fragments are not sent in HTTP requests, proxy logs, or Referer headers.
    # The account-security client removes the fragment immediately after reading it.
    return f"{base_without_fragment}#mode=reset&token={encoded_token}"


def _build_account_activation_url(token: str, *, email: str) -> str:
    source = (
        settings.password_reset_base_url_clean
        or settings.stripe_billing_portal_return_url_clean
        or "https://tomboflight.com"
    )
    parsed = urlsplit(source)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or "tomboflight.com"
    base_url = urlunsplit((scheme, netloc, "/signup.html", "", ""))
    # The token stays in the URL fragment so it is not sent in HTTP requests,
    # proxy logs, or Referer headers. The signup script removes the fragment
    # immediately after reading it.
    return (
        f"{base_url}#activation_token={quote(_normalize_text(token), safe='')}"
        f"&email={quote(_normalize_text(email).lower(), safe='')}"
    )


def _clear_password_reset_fields() -> dict[str, object]:
    return {
        "password_reset_token_hash": None,
        "password_reset_expires_at": None,
        "password_reset_requested_at": None,
        "password_reset_requested_via": None,
        "password_reset_requested_by": None,
        "password_reset_requested_by_user_id": None,
    }


def _clear_account_activation_fields() -> dict[str, object]:
    return {
        "account_activation_token_hash": None,
        "account_activation_expires_at": None,
        "account_activation_requested_at": None,
        "activation_delivery_sent": None,
        "activation_delivery_error": None,
    }


def _clear_mfa_fields() -> dict[str, object]:
    return {
        "mfa_enabled": False,
        "mfa_secret_encrypted": None,
        "mfa_backup_code_hashes": [],
        "mfa_enrolled_at": None,
        "mfa_last_verified_at": None,
        "mfa_pending_secret_encrypted": None,
        "mfa_pending_started_at": None,
    }


def build_user_response(user: dict) -> dict:
    return {
        "id": str(user["_id"]),
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user.get("role", "user"),
        "account_type": user.get("account_type"),
        "business_title": user.get("business_title"),
        "prototype_key": user.get("prototype_key"),
        "creator_credit": user.get("creator_credit"),
        "access_tier": user.get("access_tier"),
        "department_role": user.get("department_role"),
        "status": user.get("status", "active"),
        "requires_account_activation": bool(user.get("requires_account_activation")),
        "activation_delivery_sent": user.get("activation_delivery_sent"),
        "activation_delivery_error": (
            "activation_delivery_failed"
            if user.get("activation_delivery_error")
            else None
        ),
        "mfa_enabled": bool(user.get("mfa_enabled")),
        "mfa_enrolled_at": user.get("mfa_enrolled_at"),
        "created_at": user["created_at"],
        "active_project_id": user.get("active_project_id"),
        "active_family_id": user.get("active_family_id"),
        "role_codes": list(user.get("role_codes") or []),
        "capabilities": list(user.get("capabilities") or []),
        "permissions": list(user.get("permissions") or []),
        "is_admin": bool(user.get("is_admin", False)),
        "admin_roles": list(user.get("admin_roles") or []),
        "officer_roles": list(user.get("officer_roles") or []),
        "admin_permissions": list(user.get("admin_permissions") or []),
        "dashboard_type": str(user.get("dashboard_type") or "customer"),
        "allowed_rails": list(user.get("allowed_rails") or ["customer"]),
        "policy_version": user.get("policy_version"),
        "terms_accepted_at": user.get("terms_accepted_at"),
        "privacy_accepted_at": user.get("privacy_accepted_at"),
        "eligibility_attested_at": user.get("eligibility_attested_at"),
    }


def _activation_token_matches(user: dict[str, Any], token: str) -> bool:
    normalized_token = _normalize_text(token)
    expected_hash = _normalize_text(user.get("account_activation_token_hash"))
    if not normalized_token or not expected_hash:
        return False
    supplied_hash = _hash_account_activation_token(normalized_token)
    if not hmac.compare_digest(expected_hash, supplied_hash):
        return False
    expires_at = _normalize_text(user.get("account_activation_expires_at"))
    if not expires_at:
        return False
    try:
        expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except Exception:
        return False
    return expires_dt >= _now()


def _pending_activation_has_live_token(user: dict[str, Any]) -> bool:
    if not _normalize_text(user.get("account_activation_token_hash")):
        return False
    expires_at = _normalize_text(user.get("account_activation_expires_at"))
    if not expires_at:
        return False
    try:
        return datetime.fromisoformat(expires_at.replace("Z", "+00:00")) >= _now()
    except Exception:
        return False


def request_account_activation(
    email: str,
    *,
    include_delivery_status: bool = False,
) -> dict[str, object]:
    normalized_email = _normalize_text(email).lower()
    generic: dict[str, object] = {
        "success": True,
        "message": (
            "If this account is awaiting activation, a new activation link has been sent."
        ),
        "delivery_mode": "email",
    }
    db = _get_database_or_none()
    if db is None:
        if include_delivery_status:
            generic.update(
                {
                    "success": False,
                    "delivery_sent": False,
                    "delivery_error": "identity_store_unavailable",
                }
            )
        return generic

    user = db.users.find_one({"email": normalized_email})
    pending_statuses = {"pending_activation", "checkout_pending_activation"}
    if (
        user is None
        or _normalize_text(user.get("status")).lower() not in pending_statuses
        or _normalize_text(user.get("account_type")).lower() == "deleted_tombstone"
    ):
        if include_delivery_status:
            generic.update(
                {
                    "success": False,
                    "delivery_sent": False,
                    "delivery_error": "account_not_pending_activation",
                }
            )
        return generic

    token = secrets.token_urlsafe(32)
    expires_at = _account_activation_expiry_iso()
    now_iso = _now_iso()
    db.users.update_one(
        {"_id": user["_id"], "status": {"$in": list(pending_statuses)}},
        {
            "$set": {
                "account_activation_token_hash": _hash_account_activation_token(token),
                "account_activation_expires_at": expires_at,
                "account_activation_requested_at": now_iso,
                "requires_account_activation": True,
                "activation_delivery_sent": None,
                "activation_delivery_error": None,
            }
        },
    )
    activation_url = _build_account_activation_url(token, email=normalized_email)
    try:
        delivery = send_account_activation_email(
            to_email=normalized_email,
            activation_url=activation_url,
            expires_at=expires_at,
        )
    except Exception as exc:
        delivery = {
            "sent": False,
            "provider": "postmark",
            "error": type(exc).__name__,
        }
    delivery = delivery if isinstance(delivery, dict) else {}
    delivery_sent = bool(delivery.get("sent"))
    delivery_error = (
        None
        if delivery_sent
        else _normalize_text(delivery.get("error")) or "delivery_not_confirmed"
    )
    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "activation_delivery_sent": delivery_sent,
                "activation_delivery_error": delivery_error,
                "activation_delivery_provider": _normalize_text(delivery.get("provider"))
                or "postmark",
                "activation_delivery_updated_at": _now_iso(),
            }
        },
    )
    try:
        create_audit_log(
            "account_activation_requested",
            _current_user_id_from_doc(user) or None,
            "user",
            _current_user_id_from_doc(user),
            {
                "email": normalized_email,
                "delivery_sent": delivery_sent,
                "delivery_provider": _normalize_text(delivery.get("provider")) or "postmark",
            },
        )
    except Exception:
        pass
    if include_delivery_status:
        generic.update(
            {
                "success": delivery_sent,
                "delivery_sent": delivery_sent,
                "delivery_provider": _normalize_text(delivery.get("provider")) or "postmark",
                "delivery_error": delivery_error,
                "expires_at": expires_at,
            }
        )
    return generic


def register_user(payload: UserCreate) -> dict | None:
    if not payload.terms_accepted:
        raise ValueError("You must accept the Terms of Service.")
    if not payload.privacy_accepted:
        raise ValueError("You must accept the Privacy Policy.")
    if not payload.eligibility_attested:
        raise ValueError(
            "You must confirm your eligibility and authority to create the account."
        )

    validate_password_strength(payload.password)

    # Account creation must never claim success unless the account was
    # persisted. DatabaseUnavailableError is mapped to a 503 by the app.
    db = get_database()
    now_iso = _now_iso()

    normalized_email = payload.email.lower()
    existing = db.users.find_one({"email": normalized_email})
    if existing is not None:
        if (
            not existing.get("password_hash")
            and str(existing.get("status") or "").strip().lower()
            in {"pending_activation", "checkout_pending_activation"}
        ):
            if not _activation_token_matches(existing, payload.activation_token or ""):
                return None
            expected_activation_hash = _normalize_text(
                existing.get("account_activation_token_hash")
            )
            update_fields = {
                "full_name": payload.full_name.strip(),
                "role": existing.get("role") or PUBLIC_SIGNUP_ROLE,
                "account_type": existing.get("account_type") or "customer",
                "status": "active",
                "password_hash": hash_password(payload.password),
                "password_updated_at": now_iso,
                "activated_at": now_iso,
                "requires_account_activation": False,
                "session_token_version": int(existing.get("session_token_version") or 0),
                "policy_version": payload.policy_version,
                "terms_accepted_at": now_iso,
                "privacy_accepted_at": now_iso,
                "eligibility_attested_at": now_iso,
                **_clear_password_reset_fields(),
                **_clear_account_activation_fields(),
                **(
                    {}
                    if existing.get("mfa_secret_encrypted") is not None
                    else _clear_mfa_fields()
                ),
            }
            activation_result = db.users.update_one(
                {
                    "_id": existing["_id"],
                    "status": {
                        "$in": ["pending_activation", "checkout_pending_activation"]
                    },
                    "password_hash": {"$in": [None, ""]},
                    "account_activation_token_hash": expected_activation_hash,
                },
                {"$set": update_fields},
            )
            if int(getattr(activation_result, "matched_count", 0)) != 1:
                # Another request already consumed or replaced this link. A
                # token is single-use even when two submissions race.
                return None
            existing.update(update_fields)
            return existing

        return None

    user = {
        "email": normalized_email,
        "full_name": payload.full_name.strip(),
        "role": PUBLIC_SIGNUP_ROLE,
        "account_type": "customer",
        "status": "pending_activation",
        "password_hash": None,
        "password_updated_at": None,
        "created_at": now_iso,
        "last_login_at": None,
        "session_token_version": 0,
        "requires_account_activation": True,
        **_clear_account_activation_fields(),
        **_clear_password_reset_fields(),
        "password_reset_used_at": None,
        **_clear_mfa_fields(),
        "policy_version": payload.policy_version,
        "terms_accepted_at": now_iso,
        "privacy_accepted_at": now_iso,
        "eligibility_attested_at": now_iso,
    }

    result = db.users.insert_one(user)
    user["_id"] = result.inserted_id
    request_account_activation(normalized_email, include_delivery_status=True)
    return db.users.find_one({"_id": result.inserted_id}) or user


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
        if (
            _normalize_text(existing.get("status")).lower()
            in {"pending_activation", "checkout_pending_activation"}
            and not _pending_activation_has_live_token(existing)
        ):
            request_account_activation(normalized_email, include_delivery_status=True)
            return db.users.find_one({"_id": existing["_id"]}) or existing
        return existing

    now_iso = _now_iso()
    display_name = _normalize_text(full_name) or normalized_email.split("@")[0]
    user = {
        "email": normalized_email,
        "full_name": display_name,
        "role": PUBLIC_SIGNUP_ROLE,
        "account_type": "customer",
        "status": "pending_activation",
        "password_hash": None,
        "password_updated_at": None,
        "created_at": now_iso,
        "created_from": "stripe_checkout",
        "requires_account_activation": True,
        "last_login_at": None,
        "session_token_version": 0,
        **_clear_password_reset_fields(),
        "password_reset_used_at": None,
        **_clear_mfa_fields(),
        "policy_version": None,
        "terms_accepted_at": None,
        "privacy_accepted_at": None,
        "eligibility_attested_at": None,
    }

    result = db.users.insert_one(user)
    user["_id"] = result.inserted_id
    request_account_activation(normalized_email, include_delivery_status=True)
    return db.users.find_one({"_id": result.inserted_id}) or user


def authenticate_user(email: str, password: str) -> dict[str, Any] | None:
    # Authentication is fail-closed: an unavailable identity store can never
    # mint a bearer token for unverified credentials.
    db = get_database()

    user = db.users.find_one({"email": email.lower()})
    if user is None:
        return None

    if user.get("status") != "active":
        return None

    password_hash = user.get("password_hash")
    if not password_hash or not verify_password(password, password_hash):
        return None

    mfa_enabled = bool(user.get("mfa_enabled"))
    if mfa_enabled:
        challenge = create_access_token(
            {
                "sub": user["email"],
                "user_id": str(user["_id"]),
                "purpose": "mfa_login",
                "tv": _session_version(user),
            },
            expires_minutes=max(2, int(settings.mfa_challenge_expire_minutes or 10)),
        )
        return {
            "status": "mfa_required",
            "mfa_challenge_token": challenge,
        }

    if has_privileged_admin_authority(user):
        enrollment_challenge = create_access_token(
            {
                "sub": user["email"],
                "user_id": str(user["_id"]),
                "purpose": "mfa_enroll",
                "tv": _session_version(user),
            },
            expires_minutes=max(2, int(settings.mfa_challenge_expire_minutes or 10)),
        )
        return {
            "status": "mfa_enrollment_required",
            "mfa_challenge_token": enrollment_challenge,
        }

    now_iso = _now_iso()
    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "last_login_at": now_iso,
                **_clear_password_reset_fields(),
                "mfa_pending_secret_encrypted": None,
                "mfa_pending_started_at": None,
            }
        },
    )

    return {"status": "authenticated", "access_token": _build_access_token_for_user(user)}


def get_user_by_email(email: str) -> dict | None:
    db = _get_database_or_none()
    if db is None:
        return None

    return db.users.find_one({"email": email.lower()})


def get_user_by_id(user_id: str) -> dict | None:
    db = _get_database_or_none()
    if db is None:
        return None

    try:
        object_id = ObjectId(user_id)
    except Exception:
        return None

    return db.users.find_one({"_id": object_id})


def _consume_recovery_code(user: dict, code: str) -> bool:
    normalized = _normalize_text(code).lower()
    if not normalized:
        return False
    target_hash = _hash_recovery_code(
        normalized,
        user_id=str(user.get("_id") or ""),
    )
    db = get_database()
    result = db.users.update_one(
        {
            "_id": user["_id"],
            "mfa_backup_code_hashes": target_hash,
        },
        {
            "$pull": {"mfa_backup_code_hashes": target_hash},
            "$set": {"mfa_last_verified_at": _now_iso()},
        },
    )
    return int(getattr(result, "modified_count", 0)) == 1


def _begin_mfa_enrollment_for_user_document(user: dict) -> dict[str, Any]:
    if not user:
        raise ValueError("User not found.")
    if bool(user.get("mfa_enabled")):
        raise ValueError("MFA is already enabled for this account.")

    user_id = _current_user_id_from_doc(user)
    email = _normalize_text(user.get("email")).lower()
    if not user_id or not email:
        raise ValueError("User account is incomplete.")

    secret = _generate_totp_secret()
    now_iso = _now_iso()
    db = get_database()
    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "mfa_pending_secret_encrypted": _mfa_encrypt_secret(secret, user_id=user_id),
                "mfa_pending_started_at": now_iso,
            }
        },
    )
    setup_token = create_access_token(
        {
            "sub": email,
            "user_id": user_id,
            "purpose": "mfa_enroll_verify",
            "tv": _session_version(user),
        },
        expires_minutes=max(2, int(settings.mfa_challenge_expire_minutes or 10)),
    )
    return {
        "setup_token": setup_token,
        "secret": secret,
        "otpauth_url": _build_mfa_otpauth_uri(secret, email=email),
    }


def begin_mfa_enrollment(challenge_token: str) -> dict[str, Any]:
    payload = decode_access_token(_normalize_text(challenge_token))
    if not payload or _normalize_text(payload.get("purpose")) != "mfa_enroll":
        raise ValueError("Invalid MFA challenge token.")
    user = get_user_by_email(_normalize_text(payload.get("sub")).lower())
    if not user:
        raise ValueError("User not found.")
    user_id = str(user.get("_id") or "")
    if _normalize_text(payload.get("user_id")) != user_id:
        raise ValueError("Invalid MFA challenge token.")
    _assert_mfa_token_version(payload, user, token_label="MFA challenge token")
    return _begin_mfa_enrollment_for_user_document(user)


def begin_mfa_enrollment_for_user(user: dict) -> dict[str, Any]:
    return _begin_mfa_enrollment_for_user_document(user)


def verify_mfa_enrollment(setup_token: str, code: str) -> dict[str, Any]:
    payload = decode_access_token(_normalize_text(setup_token))
    if not payload or _normalize_text(payload.get("purpose")) != "mfa_enroll_verify":
        raise ValueError("Invalid MFA setup token.")
    user = get_user_by_email(_normalize_text(payload.get("sub")).lower())
    if not user:
        raise ValueError("User not found.")
    user_id = str(user.get("_id") or "")
    if _normalize_text(payload.get("user_id")) != user_id:
        raise ValueError("Invalid MFA setup token.")
    _assert_mfa_token_version(payload, user, token_label="MFA setup token")
    pending_secret = _mfa_decrypt_secret(
        _normalize_text(user.get("mfa_pending_secret_encrypted")),
        user_id=user_id,
    )
    if not pending_secret:
        raise ValueError("No pending MFA enrollment was found.")
    if not _verify_totp(pending_secret, code):
        raise ValueError("Invalid MFA code.")
    backup_code_count = max(4, int(settings.mfa_backup_code_count or 8))
    backup_codes = [secrets.token_hex(8) for _ in range(backup_code_count)]
    backup_hashes = [
        _hash_recovery_code(value, user_id=user_id)
        for value in backup_codes
    ]
    now_iso = _now_iso()
    db = get_database()
    encrypted_secret = _mfa_encrypt_secret(pending_secret, user_id=user_id)
    next_session_version = _session_version(user) + 1
    update_result = db.users.update_one(
        {
            "_id": user["_id"],
            "mfa_pending_secret_encrypted": user.get(
                "mfa_pending_secret_encrypted"
            ),
            "session_token_version": user.get("session_token_version"),
        },
        {
            "$set": {
                "mfa_enabled": True,
                "mfa_secret_encrypted": encrypted_secret,
                "mfa_backup_code_hashes": backup_hashes,
                "mfa_enrolled_at": now_iso,
                "mfa_last_verified_at": now_iso,
                "mfa_pending_secret_encrypted": None,
                "mfa_pending_started_at": None,
                "last_login_at": now_iso,
                "session_token_version": next_session_version,
            },
        },
    )
    if int(getattr(update_result, "matched_count", 0)) != 1:
        raise ValueError("MFA enrollment changed before verification completed.")
    try:
        create_audit_log(
            "mfa_enrollment_verified",
            user_id,
            "user",
            user_id,
            {"email": _normalize_text(user.get("email")).lower()},
        )
    except Exception:
        pass
    refreshed_user = db.users.find_one({"_id": user["_id"]}) or {
        **user,
        "session_token_version": next_session_version,
    }
    refreshed_user["mfa_enabled"] = True
    refreshed_user["mfa_secret_encrypted"] = encrypted_secret
    return {
        "access_token": _build_access_token_for_user(refreshed_user),
        "backup_codes": backup_codes,
    }


def verify_mfa_login_challenge(
    challenge_token: str,
    *,
    code: str | None = None,
    recovery_code: str | None = None,
) -> dict[str, Any]:
    payload = decode_access_token(_normalize_text(challenge_token))
    if not payload or _normalize_text(payload.get("purpose")) != "mfa_login":
        raise ValueError("Invalid MFA challenge token.")
    user = get_user_by_email(_normalize_text(payload.get("sub")).lower())
    if not user:
        raise ValueError("User not found.")
    user_id = str(user.get("_id") or "")
    if _normalize_text(payload.get("user_id")) != user_id:
        raise ValueError("Invalid MFA challenge token.")
    _assert_mfa_token_version(payload, user, token_label="MFA challenge token")
    if not bool(user.get("mfa_enabled")):
        raise ValueError("MFA is not enabled for this account.")
    secret = _mfa_decrypt_secret(_normalize_text(user.get("mfa_secret_encrypted")), user_id=user_id)
    success = False
    if _normalize_text(code):
        success = _verify_totp(secret, _normalize_text(code))
    elif _normalize_text(recovery_code):
        success = _consume_recovery_code(user, _normalize_text(recovery_code))
    if not success:
        try:
            create_audit_log(
                "mfa_login_challenge_failed",
                user_id,
                "user",
                user_id,
                {"email": _normalize_text(user.get("email")).lower()},
            )
        except Exception:
            pass
        raise ValueError("Invalid MFA verification code.")
    now_iso = _now_iso()
    db = get_database()
    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"mfa_last_verified_at": now_iso, "last_login_at": now_iso}},
    )
    try:
        create_audit_log(
            "mfa_login_challenge_succeeded",
            user_id,
            "user",
            user_id,
            {"email": _normalize_text(user.get("email")).lower()},
        )
    except Exception:
        pass
    return {"access_token": _build_access_token_for_user(user)}


def disable_mfa_for_user(
    *,
    user: dict[str, Any],
    current_password: str,
    code: str | None,
    recovery_code: str | None,
    actor_user_id: str,
) -> None:
    password_hash = _normalize_text(user.get("password_hash"))
    if not verify_password(current_password, password_hash):
        raise ValueError("Current password is incorrect.")
    user_id = str(user.get("_id") or "")
    secret = _mfa_decrypt_secret(_normalize_text(user.get("mfa_secret_encrypted")), user_id=user_id)
    verified = False
    if _normalize_text(code):
        verified = _verify_totp(secret, _normalize_text(code))
    elif _normalize_text(recovery_code):
        verified = _consume_recovery_code(user, _normalize_text(recovery_code))
    if not verified:
        raise ValueError("MFA verification failed.")
    db = get_database()
    next_session_version = _session_version(user) + 1
    update_result = db.users.update_one(
        {
            "_id": user["_id"],
            "session_token_version": user.get("session_token_version"),
        },
        {
            "$set": {
                **_clear_mfa_fields(),
                "session_token_version": next_session_version,
            },
        },
    )
    if int(getattr(update_result, "matched_count", 0)) != 1:
        raise ValueError("Account security changed before MFA could be disabled.")
    try:
        create_audit_log(
            "mfa_disabled",
            actor_user_id,
            "user",
            user_id,
            {"email": _normalize_text(user.get("email")).lower()},
        )
    except Exception:
        pass


def admin_reset_user_security(
    *,
    target_user_id: str,
    actor_user_id: str,
    actor_email: str = "",
) -> None:
    user = get_user_by_id(target_user_id)
    if not user:
        raise ValueError("User account not found.")
    if is_canonical_ceo_email(user.get("email")) and not is_canonical_ceo_email(actor_email):
        raise ValueError("Only the canonical CEO can reset CEO account security.")
    next_version = _session_version(user) + 1
    db = get_database()
    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "session_token_version": next_version,
                **_clear_mfa_fields(),
            }
        },
    )
    try:
        create_audit_log(
            "admin_security_reset",
            actor_user_id,
            "user",
            str(user["_id"]),
            {"email": _normalize_text(user.get("email")).lower()},
        )
    except Exception:
        pass


def revoke_user_sessions(
    *,
    user_id: str,
    actor_user_id: str | None = None,
    reason: str = "logout",
) -> bool:
    user = get_user_by_id(user_id)
    if not user:
        return False
    next_version = _session_version(user) + 1
    db = get_database()
    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "session_token_version": next_version,
                "last_logout_at": _now_iso(),
            }
        },
    )
    try:
        create_audit_log(
            "session_revoked",
            actor_user_id or user_id,
            "user",
            str(user["_id"]),
            {
                "reason": _normalize_text(reason) or "logout",
                "email": _normalize_text(user.get("email")).lower(),
                "session_token_version": next_version,
            },
        )
    except Exception:
        pass
    return True


def request_password_reset(
    email: str,
    *,
    requested_via: str = "self_service",
    requested_by_user_id: str | None = None,
    requested_by: str | None = None,
    expose_token: bool = False,
    include_delivery_status: bool = False,
) -> dict[str, object]:
    normalized_email = _normalize_text(email).lower()
    generic_message = (
        "If this account exists, a password reset link has been sent to that email address."
    )
    generic_response: dict[str, object] = {
        "success": True,
        "message": generic_message,
        "delivery_mode": "email",
    }

    db = _get_database_or_none()
    if db is None:
        if include_delivery_status:
            generic_response.update(
                {
                    "success": False,
                    "delivery_sent": False,
                    "delivery_provider": "postmark",
                    "delivery_error": "identity_store_unavailable",
                    "failure_count": 1,
                }
            )
        return generic_response

    user = db.users.find_one({"email": normalized_email})
    if user is None:
        if include_delivery_status:
            generic_response.update(
                {
                    "success": False,
                    "delivery_sent": False,
                    "delivery_provider": "postmark",
                    "delivery_error": "account_not_found",
                    "failure_count": 1,
                }
            )
        return generic_response

    account_status = _normalize_text(user.get("status")).lower()
    account_type = _normalize_text(user.get("account_type")).lower()
    if account_status not in {"", "active"} or account_type == "deleted_tombstone":
        # Do not create a credential-recovery path for suspended, archived, or
        # permanently deleted identities. Self-service callers still receive
        # the generic response so account state cannot be enumerated.
        if include_delivery_status:
            generic_response.update(
                {
                    "success": False,
                    "reset_persisted": False,
                    "delivery_sent": False,
                    "delivery_provider": "postmark",
                    "delivery_error": "account_not_active",
                    "failure_count": 1,
                }
            )
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
                "admin_assisted": _normalize_text(requested_via).lower() == "admin_assist",
            },
        )
    except Exception:
        pass

    reset_url = _build_password_reset_url(token)

    # Self-service responses remain generic to prevent account enumeration.
    # The authenticated admin-assist flow may request a safe delivery result
    # so the Control Center does not claim an email was sent when it was not.
    if not bool(expose_token):
        try:
            delivery = send_password_reset_email(
                to_email=normalized_email,
                reset_url=reset_url,
                expires_at=expires_at,
            )
        except Exception as exc:
            delivery = {
                "sent": False,
                "provider": "postmark",
                "error": type(exc).__name__,
            }
        if include_delivery_status:
            delivery = delivery if isinstance(delivery, dict) else {}
            delivery_sent = bool(delivery.get("sent"))
            generic_response.update(
                {
                    "success": delivery_sent,
                    "reset_persisted": True,
                    "delivery_sent": delivery_sent,
                    "delivery_provider": _normalize_text(delivery.get("provider")) or "postmark",
                    "delivery_error": (
                        None
                        if delivery_sent
                        else _normalize_text(delivery.get("error")) or "delivery_not_confirmed"
                    ),
                    "failure_count": 0 if delivery_sent else 1,
                }
            )

    if bool(expose_token):
        generic_response["reset_token"] = token
        generic_response["reset_url"] = reset_url
        generic_response["expires_at"] = expires_at

    return generic_response


def request_account_recovery(
    email: str,
    *,
    include_delivery_status: bool = False,
) -> dict[str, object]:
    """Send the recovery email appropriate for the account's current state.

    Public callers always receive the same response. Internally, an unfinished
    account receives a fresh activation link and an active account receives a
    password-reset link. Suspended, archived, deleted, and unknown identities
    receive no credential path and remain indistinguishable to the caller.
    """

    normalized_email = _normalize_text(email).lower()
    generic_response: dict[str, object] = {
        "success": True,
        "message": (
            "If this email is connected to an account, the appropriate secure "
            "access link has been sent."
        ),
        "delivery_mode": "email",
    }

    db = _get_database_or_none()
    if db is None:
        if include_delivery_status:
            generic_response.update(
                {
                    "success": False,
                    "delivery_sent": False,
                    "delivery_error": "identity_store_unavailable",
                    "recovery_mode": "none",
                }
            )
        return generic_response

    user = db.users.find_one({"email": normalized_email})
    if user is None or _normalize_text(user.get("account_type")).lower() == "deleted_tombstone":
        if include_delivery_status:
            generic_response.update(
                {
                    "success": False,
                    "delivery_sent": False,
                    "delivery_error": "account_not_found",
                    "recovery_mode": "none",
                }
            )
        return generic_response

    account_status = _normalize_text(user.get("status")).lower()
    delivery: dict[str, object]
    recovery_mode = "none"
    if account_status in {"pending_activation", "checkout_pending_activation"}:
        recovery_mode = "activation"
        delivery = request_account_activation(
            normalized_email,
            include_delivery_status=include_delivery_status,
        )
    elif account_status in {"", "active"}:
        recovery_mode = "password_reset"
        delivery = request_password_reset(
            normalized_email,
            include_delivery_status=include_delivery_status,
        )
    else:
        delivery = {
            "success": False,
            "delivery_sent": False,
            "delivery_error": "account_not_active",
        }

    if include_delivery_status:
        generic_response.update(
            {
                "success": bool(delivery.get("success")),
                "delivery_sent": bool(delivery.get("delivery_sent")),
                "delivery_provider": delivery.get("delivery_provider"),
                "delivery_error": delivery.get("delivery_error"),
                "recovery_mode": recovery_mode,
            }
        )
    return generic_response


def reset_password_with_token(token: str, new_password: str) -> dict[str, object]:
    normalized_token = _normalize_text(token)
    if not normalized_token:
        raise ValueError("Password reset token is required.")

    validate_password_strength(new_password)

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
        "session_token_version": _session_version(user) + 1,
        **_clear_password_reset_fields(),
    }
    consume_result = db.users.update_one(
        {
            "_id": user["_id"],
            "password_reset_token_hash": token_hash,
            "password_reset_expires_at": user.get("password_reset_expires_at"),
            "status": user.get("status"),
        },
        {"$set": update_fields},
    )
    if int(getattr(consume_result, "matched_count", 0)) != 1:
        raise ValueError("Password reset token is invalid, expired, or already used.")

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

    # Notify user (best-effort).
    try:
        send_password_changed_email(
            to_email=_normalize_text(user.get("email")).lower()
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
    validate_password_strength(new_password)

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
                "session_token_version": _session_version(user) + 1,
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

    # Notify user (best-effort).
    try:
        send_password_changed_email(
            to_email=_normalize_text(user.get("email")).lower()
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
    admin_email: str = "",
) -> dict[str, object]:
    user = get_user_by_id(user_id)
    if user is None:
        raise ValueError("User account not found.")
    if is_canonical_ceo_email(user.get("email")) and not is_canonical_ceo_email(admin_email):
        raise ValueError("Only the canonical CEO can issue a CEO password reset.")
    if (
        _normalize_text(user.get("status")).lower() == "permanently_deleted"
        or _normalize_text(user.get("account_type")).lower() == "deleted_tombstone"
    ):
        raise ValueError("A permanently deleted account cannot receive a password reset.")

    response = request_password_reset(
        _normalize_text(user.get("email")).lower(),
        requested_via="admin_assist",
        requested_by_user_id=admin_user_id,
        requested_by=admin_display,
        # Deliver the reset link to the verified account email. Returning the
        # raw reset token to an administrator would bypass customer control of
        # the mailbox and could leak into operation evidence or browser logs.
        expose_token=False,
        include_delivery_status=True,
    )
    response["message"] = (
        "Password-reset link sent to the account email."
        if bool(response.get("delivery_sent"))
        else "Password reset was not delivered; review the operation evidence and email configuration."
    )
    return response
