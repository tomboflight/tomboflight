from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.package_catalog import get_package
from app.core.security import decode_access_token
from app.services.auth_service import get_user_by_email
from app.services.order_service import get_orders_for_user
from app.services.project_entitlement_service import list_user_project_entitlements

COOKIE_NAME = "tol_access_token"

INTERNAL_ADMIN_KEYS = {
    "admin",
    "super_admin",
    "root_admin",
    "platform_admin",
    "operations_admin",
    "finance_admin",
    "marketing_admin",
    "executive_technology",
    "operations",
    "finance",
    "marketing",
}

ALLOWED_COOKIE_AUTH_ORIGINS = {
    "https://tomboflight.com",
    "https://www.tomboflight.com",
    "http://127.0.0.1:5500",
    "http://localhost:5500",
}

bearer_scheme = HTTPBearer(auto_error=False)


def _normalize_value(value) -> str:
    return str(value or "").strip().lower()


def _normalize_user(user: dict, payload: dict) -> dict:
    normalized_user = dict(user)

    raw_id = (
        normalized_user.get("id")
        or normalized_user.get("_id")
        or payload.get("user_id")
    )

    if raw_id is not None:
        normalized_user["id"] = str(raw_id)

    if "user_id" not in normalized_user and raw_id is not None:
        normalized_user["user_id"] = str(raw_id)

    return normalized_user


def _extract_request_origin(request: Request) -> str:
    origin = request.headers.get("origin")
    if origin:
        return origin.strip()

    referer = request.headers.get("referer")
    if referer:
        parsed = urlparse(referer)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"

    return ""


def _is_unsafe_method(method: str) -> bool:
    return method.upper() in {"POST", "PUT", "PATCH", "DELETE"}


def _enforce_cookie_auth_origin(request: Request) -> None:
    if not _is_unsafe_method(request.method):
        return

    origin = _extract_request_origin(request)
    if not origin or origin not in ALLOWED_COOKIE_AUTH_ORIGINS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin is not allowed for cookie-authenticated request.",
        )


def _get_token_from_request(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> tuple[str | None, str | None]:
    if credentials and credentials.credentials:
        return credentials.credentials, "bearer"

    cookie_token = request.cookies.get(COOKIE_NAME)
    if cookie_token:
        return cookie_token, "cookie"

    return None, None


def _has_internal_admin_access(user: dict) -> bool:
    values = {
        _normalize_value(user.get("role")),
        _normalize_value(user.get("access_tier")),
        _normalize_value(user.get("department_role")),
    }
    return any(value in INTERNAL_ADMIN_KEYS for value in values if value)


def has_internal_admin_access(user: dict) -> bool:
    return _has_internal_admin_access(user)


def _current_user_id(user: dict) -> str:
    raw_id = user.get("id") or user.get("_id") or user.get("user_id")
    return str(raw_id or "").strip()


def _current_user_email(user: dict) -> str:
    return str(user.get("email") or "").strip().lower()


def _collect_capabilities_from_mapping(
    target: set[str],
    values: dict | None,
) -> None:
    if not isinstance(values, dict):
        return

    for key, enabled in values.items():
        normalized_key = _normalize_value(key)
        if normalized_key.startswith("can_") and bool(enabled):
            target.add(normalized_key)


def _is_paid_package_order(order: dict | None) -> bool:
    if not isinstance(order, dict):
        return False

    item_type = _normalize_value(order.get("item_type") or "package")
    status = _normalize_value(order.get("status"))

    return item_type == "package" and status in {
        "paid",
        "complete",
        "completed",
        "succeeded",
    }


def get_user_package_capabilities(user: dict) -> set[str]:
    if has_internal_admin_access(user):
        return {"*"}

    capabilities: set[str] = set()
    user_id = _current_user_id(user)
    user_email = _current_user_email(user)

    if user_id:
        entitlements = list_user_project_entitlements(user_id, active_only=True)
        for entitlement in entitlements:
            _collect_capabilities_from_mapping(
                capabilities,
                entitlement.get("resolved_entitlements"),
            )

    try:
        orders = get_orders_for_user(user)
    except Exception:
        orders = []

    for order in orders:
        if not _is_paid_package_order(order):
            continue

        package_code = str(
            order.get("package_code") or order.get("package_slug") or ""
        ).strip()
        package = get_package(package_code)
        _collect_capabilities_from_mapping(capabilities, package)

    return capabilities


def has_package_capability(user: dict, capability: str) -> bool:
    if has_internal_admin_access(user):
        return True

    normalized_capability = _normalize_value(capability)
    if not normalized_capability:
        return False

    return normalized_capability in get_user_package_capabilities(user)


def has_any_package_capability(user: dict, *capabilities: str) -> bool:
    normalized_capabilities = [
        _normalize_value(capability)
        for capability in capabilities
        if _normalize_value(capability)
    ]
    if not normalized_capabilities:
        return False

    if has_internal_admin_access(user):
        return True

    user_capabilities = get_user_package_capabilities(user)
    return any(capability in user_capabilities for capability in normalized_capabilities)


def require_package_capability(
    user: dict,
    capability: str,
    *,
    detail: str = "Your active package does not include this feature.",
) -> dict:
    if not has_package_capability(user, capability):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )
    return user


def require_any_package_capability(
    user: dict,
    *capabilities: str,
    detail: str = "Your active package does not include this feature.",
) -> dict:
    if not has_any_package_capability(user, *capabilities):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )
    return user


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    token, source = _get_token_from_request(request, credentials)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )

    if source == "cookie":
        _enforce_cookie_auth_origin(request)

    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
        )

    user = get_user_by_email(email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    normalized_user = _normalize_user(user, payload)

    payload_user_id = _normalize_value(payload.get("user_id"))
    actual_user_id = _normalize_value(normalized_user.get("id"))
    if payload_user_id and actual_user_id and payload_user_id != actual_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
        )

    payload_email = _normalize_value(email)
    actual_email = _normalize_value(normalized_user.get("email"))
    if payload_email and actual_email and payload_email != actual_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
        )

    status_value = _normalize_value(normalized_user.get("status"))
    if status_value not in {"", "active"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive.",
        )

    return normalized_user


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if not has_internal_admin_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user
