from datetime import UTC, datetime, timedelta
from typing import Any, cast

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

SECRET_KEY: str = str(settings.secret_key or "change-me")
ALGORITHM: str = str(settings.algorithm or "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(settings.access_token_expire_minutes or 60)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(data: dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    token = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=cast(Any, ALGORITHM),
    )
    return cast(str, token)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=cast(Any, [ALGORITHM]),
        )
        return cast(dict[str, Any], payload)
    except JWTError:
        return None