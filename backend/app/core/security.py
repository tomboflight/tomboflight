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


def create_access_token(data: dict[str, Any]) -> str:
    to_encode = data.copy()
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

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
