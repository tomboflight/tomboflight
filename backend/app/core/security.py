import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings


def _resolve_secret_key() -> str:
    secret_key = str(settings.secret_key or "").strip()
    environment = str(settings.environment or "development").strip().lower()

    if not secret_key:
        raise RuntimeError("SECRET_KEY is not configured.")

    if secret_key == "change-me" and environment not in {
        "development",
        "dev",
        "local",
        "test",
    }:
        raise RuntimeError(
            "SECRET_KEY must be set to a unique value outside development."
        )

    return secret_key


SECRET_KEY: str = _resolve_secret_key()
ALGORITHM: str = str(settings.algorithm or "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(settings.access_token_expire_minutes or 60)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    if not isinstance(password, str) or not password.strip():
        raise ValueError("Password cannot be empty.")
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    if not password or not hashed:
        return False
    return pwd_context.verify(password, hashed)


def create_access_token(data: dict[str, Any], *, expires_minutes: int | None = None) -> str:
    to_encode = data.copy()
    now = datetime.now(UTC)
    lifetime_minutes = (
        ACCESS_TOKEN_EXPIRE_MINUTES
        if expires_minutes is None
        else max(1, int(expires_minutes))
    )
    expire = now + timedelta(minutes=lifetime_minutes)

    to_encode.update(
        {
            "iat": now,
            "nbf": now,
            "exp": expire,
        }
    )

    token = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=cast(Any, ALGORITHM),
    )
    return cast(str, token)


def decode_access_token(token: str) -> dict[str, Any] | None:
    if not token or not isinstance(token, str):
        return None

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=cast(Any, [ALGORITHM]),
        )
        if not isinstance(payload, dict):
            return None
        return cast(dict[str, Any], payload)
    except JWTError:
        return None


def _csrf_sig(user_id: str, nonce: str, expires_at: int) -> str:
    payload = f"{user_id}:{nonce}:{expires_at}".encode("utf-8")
    secret = SECRET_KEY.encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def create_csrf_token(user_id: str, *, ttl_minutes: int) -> str:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        raise ValueError("user_id is required for CSRF token issuance.")
    nonce = secrets.token_urlsafe(24)
    expires_at = int(
        (datetime.now(UTC) + timedelta(minutes=max(1, int(ttl_minutes)))).timestamp()
    )
    signature = _csrf_sig(normalized_user_id, nonce, expires_at)
    return f"{nonce}.{expires_at}.{signature}"


def verify_csrf_token(token: str, *, user_id: str) -> bool:
    normalized = str(token or "").strip()
    normalized_user_id = str(user_id or "").strip()
    if not normalized or not normalized_user_id:
        return False
    try:
        nonce, expires_at_raw, signature = normalized.split(".", 2)
        expires_at = int(expires_at_raw)
    except Exception:
        return False
    if expires_at < int(datetime.now(UTC).timestamp()):
        return False
    expected = _csrf_sig(normalized_user_id, nonce, expires_at)
    return hmac.compare_digest(signature, expected)
