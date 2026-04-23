from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from bson import ObjectId
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.core.admin_permission_registry import (
    CAPABILITY_PERMISSIONS,
    ROLE_CAPABILITIES,
    ROLE_PERMISSION_MAP,
)
from app.core.package_catalog import get_package
from app.core.role_catalog import (
    INTERNAL_ADMIN_ROLE_CODES,
    SUPER_ADMIN_ROLE_CODES,
    collect_role_codes,
    has_internal_admin_role,
    normalize_role_code,
)
from app.core.security import decode_access_token, verify_csrf_token
from app.database import get_database
from app.services.audit_log_service import write_audit_log
from app.services.auth_service import get_user_by_email
from app.services.control_layer_service import create_workflow_event
from app.services.order_service import get_orders_for_user
from app.services.project_entitlement_service import list_user_project_entitlements
from app.services.project_membership_service import (
    get_project_access_snapshot,
    list_accessible_project_ids,
)

COOKIE_NAME = "tol_access_token"
CSRF_COOKIE_NAME = "tol_csrf_token"

INTERNAL_ADMIN_KEYS = set(INTERNAL_ADMIN_ROLE_CODES)
SUPER_ADMIN_KEYS = set(SUPER_ADMIN_ROLE_CODES)

bearer_scheme = HTTPBearer(auto_error=False)


def _normalize_value(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_user(user: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
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


def _normalize_origin(value: Any) -> str:
    return str(value or "").strip().rstrip("/")


def _is_unsafe_method(method: str) -> bool:
    return method.upper() in {"POST", "PUT", "PATCH", "DELETE"}


def _is_public_password_reset_route(request: Request) -> bool:
    path = str(request.url.path or "").rstrip("/")
    return path in {
        "/auth/password-reset/request",
        "/auth/password-reset/confirm",
    }


def _is_cookie_csrf_exempt_route(request: Request) -> bool:
    path = str(request.url.path or "").rstrip("/")
    return path in {
        "/auth/logout",
        "/auth/mfa/enroll/begin",
        "/auth/mfa/enroll/verify",
        "/auth/mfa/login/verify",
        "/auth/password-reset/request",
        "/auth/password-reset/confirm",
        "/webhooks/stripe",
    }


def _allowed_cookie_auth_origins() -> set[str]:
    configured = settings.allowed_origins_list or []
    normalized = {
        _normalize_origin(origin)
        for origin in configured
        if _normalize_origin(origin)
    }
    normalized.discard("*")

    if normalized:
        return normalized

    defaults = {
        "https://tomboflight.com",
        "https://www.tomboflight.com",
    }
    if getattr(settings, "local_dev_cors_enabled_effective", False):
        defaults.update(
            {
                "http://127.0.0.1:5500",
                "http://localhost:5500",
                "http://[::1]:5500",
                "http://127.0.0.1:8000",
                "http://localhost:8000",
                "http://[::1]:8000",
                "http://127.0.0.1:8081",
                "http://localhost:8081",
                "http://[::1]:8081",
            }
        )
    return defaults


def _enforce_cookie_auth_origin(request: Request) -> None:
    if not _is_unsafe_method(request.method):
        return

    # Public password-reset routes must remain accessible even when a stale
    # auth cookie is present in the browser.
    if _is_public_password_reset_route(request):
        return

    origin = _normalize_origin(_extract_request_origin(request))
    if not origin or origin not in _allowed_cookie_auth_origins():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin is not allowed for cookie-authenticated request.",
        )


def _enforce_cookie_auth_csrf(request: Request, *, user_id: str) -> None:
    if not _is_unsafe_method(request.method):
        return
    if _is_cookie_csrf_exempt_route(request):
        return
    header_token = str(request.headers.get("x-csrf-token") or "").strip()
    cookie_token = str(request.cookies.get(CSRF_COOKIE_NAME) or "").strip()
    if not header_token or not cookie_token or header_token != cookie_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed for cookie-authenticated request.",
        )
    if not verify_csrf_token(cookie_token, user_id=user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token is invalid or expired.",
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


def _has_internal_admin_access(user: dict[str, Any]) -> bool:
    return has_internal_admin_role(
        (
            user.get("role"),
            user.get("access_tier"),
            user.get("department_role"),
        )
    )


def has_internal_admin_access(user: dict[str, Any]) -> bool:
    return _has_internal_admin_access(user)


def is_customer_account(user: dict[str, Any]) -> bool:
    return not has_internal_admin_access(user)


def _current_user_id(user: dict[str, Any]) -> str:
    raw_id = user.get("id") or user.get("_id") or user.get("user_id")
    return str(raw_id or "").strip()


def _current_user_email(user: dict[str, Any]) -> str:
    return str(user.get("email") or "").strip().lower()


def _collect_capabilities_from_mapping(
    target: set[str],
    values: dict[str, Any] | None,
) -> None:
    if not isinstance(values, dict):
        return

    for key, enabled in values.items():
        normalized_key = _normalize_value(key)
        if normalized_key.startswith("can_") and bool(enabled):
            target.add(normalized_key)


def _is_paid_package_order(order: dict[str, Any] | None) -> bool:
    if not isinstance(order, dict):
        return False

    item_type = _normalize_value(order.get("item_type") or "package")
    status_value = _normalize_value(order.get("status"))

    return item_type == "package" and status_value in {
        "paid",
        "complete",
        "completed",
        "succeeded",
    }


def _list_active_entitlements_for_user(
    user_id: str,
    *,
    user_email: str = "",
) -> list[dict[str, Any]]:
    if not user_id and not user_email:
        return []

    try:
        return list_user_project_entitlements(
            user_id,
            email=user_email,
            active_only=True,
        )
    except TypeError:
        try:
            entitlements = list_user_project_entitlements(
                user_id,
            )
        except Exception:
            return []

        return [
            entitlement
            for entitlement in entitlements
            if _normalize_value(entitlement.get("status")) == "active"
        ]
    except Exception:
        return []


def get_user_package_capabilities(user: dict[str, Any]) -> set[str]:
    capabilities: set[str] = set()

    if not is_customer_account(user):
        return capabilities

    user_id = _current_user_id(user)
    user_email = _current_user_email(user)

    if user_id or user_email:
        entitlements = _list_active_entitlements_for_user(
            user_id,
            user_email=user_email,
        )
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


def has_package_capability(
    user: dict[str, Any],
    capability: str,
    *,
    allow_internal_admin: bool = False,
) -> bool:
    if allow_internal_admin and has_internal_admin_access(user):
        return True

    normalized_capability = _normalize_value(capability)
    if not normalized_capability:
        return False

    if not is_customer_account(user):
        return False

    return normalized_capability in get_user_package_capabilities(user)


def has_any_package_capability(
    user: dict[str, Any],
    *capabilities: str,
    allow_internal_admin: bool = False,
) -> bool:
    normalized_capabilities = [
        _normalize_value(capability)
        for capability in capabilities
        if _normalize_value(capability)
    ]
    if not normalized_capabilities:
        return False

    if allow_internal_admin and has_internal_admin_access(user):
        return True

    if not is_customer_account(user):
        return False

    user_capabilities = get_user_package_capabilities(user)
    return any(capability in user_capabilities for capability in normalized_capabilities)


def require_package_capability(
    user: dict[str, Any],
    capability: str,
    *,
    detail: str = "Your active package does not include this feature.",
    allow_internal_admin: bool = False,
) -> dict[str, Any]:
    if not has_package_capability(
        user,
        capability,
        allow_internal_admin=allow_internal_admin,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )
    return user


def require_any_package_capability(
    user: dict[str, Any],
    *capabilities: str,
    detail: str = "Your active package does not include this feature.",
    allow_internal_admin: bool = False,
) -> dict[str, Any]:
    if not has_any_package_capability(
        user,
        *capabilities,
        allow_internal_admin=allow_internal_admin,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )
    return user


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
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

    payload_token_version = _normalize_value(payload.get("tv"))
    user_token_version = _normalize_value(normalized_user.get("session_token_version") or 0)
    # Backward compatibility: legacy tokens issued before token-version support
    # may not include "tv". We only permit missing version when the account has
    # never been version-bumped (still at zero).
    token_version_missing_for_legacy_user = (
        payload_token_version == "" and user_token_version == "0"
    )
    if payload_token_version != user_token_version and not token_version_missing_for_legacy_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked. Please log in again.",
        )

    if _has_internal_admin_access(normalized_user) and bool(
        normalized_user.get("mfa_enabled")
    ):
        if not bool(payload.get("mfa")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="MFA verification is required for this session.",
            )

    if source == "cookie":
        _enforce_cookie_auth_csrf(
            request,
            user_id=_current_user_id(normalized_user) or _current_user_email(normalized_user),
        )

    return normalized_user


def require_admin(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if not has_internal_admin_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user


def require_super_admin(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    context = _get_or_resolve_access_context(
        current_user,
        project_id=_extract_project_id_from_request(request),
    )
    role_codes = {
        _normalize_value(role_code)
        for role_code in (context.get("role_codes") or [])
        if _normalize_value(role_code)
    }
    role_codes.update(
        collect_role_codes(
            (
                current_user.get("role"),
                current_user.get("access_tier"),
                current_user.get("department_role"),
            )
        )
    )
    if role_codes.intersection(SUPER_ADMIN_KEYS):
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Super Admin role is required.",
    )


WORKFLOW_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "": {"draft", "purchased", "build_ready"},
    "draft": {"purchased", "build_ready"},
    "purchased": {"build_ready"},
    "build_ready": {"in_production", "archived"},
    "in_production": {"qa_review", "client_review", "archived"},
    "qa_review": {"client_review", "in_production", "archived"},
    "client_review": {"delivered", "in_production", "archived"},
    "delivered": {"archived"},
    "archived": set(),
}

WORKFLOW_PHASE_BY_STATE: dict[str, str] = {
    "draft": "created",
    "purchased": "checkout_completed",
    "build_ready": "intake_approved",
    "in_production": "build_started",
    "qa_review": "quality_review",
    "client_review": "client_review",
    "delivered": "delivery_complete",
    "archived": "archived",
}

BYTES_PER_GB = 1024 * 1024 * 1024


def _db():
    db = get_database()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database is not connected.",
        )
    return db


def _extract_project_id_from_request(request: Request) -> str | None:
    def _safe_get(value: Any, key: str) -> Any:
        getter = getattr(value, "get", None)
        if callable(getter):
            return getter(key)
        return None

    path_params = getattr(request, "path_params", None)
    query_params = getattr(request, "query_params", None)

    candidates = [
        _safe_get(path_params, "project_id"),
        _safe_get(query_params, "project_id"),
    ]
    for candidate in candidates:
        normalized = _normalize_value(candidate)
        if normalized:
            return normalized
    return None


def _extract_workspace_identifiers(request: Request) -> tuple[str, str, str]:
    return (
        _normalize_value(
            request.path_params.get("project_id") or request.query_params.get("project_id")
        ),
        _normalize_value(
            request.path_params.get("family_id") or request.query_params.get("family_id")
        ),
        _normalize_value(
            request.path_params.get("member_id") or request.query_params.get("member_id")
        ),
    )


def _load_user_by_id(user_id: str) -> dict[str, Any] | None:
    if not user_id:
        return None
    db = _db()
    users = db["users"]
    if ObjectId.is_valid(user_id):
        user = users.find_one({"_id": ObjectId(user_id)})
        if user is not None:
            return user
    return users.find_one({"$or": [{"id": user_id}, {"user_id": user_id}]})


def _collect_role_codes_for_user(user: dict[str, Any]) -> set[str]:
    role_codes = collect_role_codes(
        user.get(field_name) for field_name in ("role", "access_tier", "department_role")
    )

    user_id = _current_user_id(user)
    if user_id:
        assignments = _db()["user_role_assignments"].find(
            {"user_id": user_id, "status": {"$in": ["active", "enabled", ""]}}
        )
        for assignment in assignments:
            role_code = normalize_role_code(assignment.get("role_code"))
            if role_code:
                role_codes.add(role_code)
    return role_codes


def _collect_capabilities_for_roles(role_codes: set[str]) -> set[str]:
    capabilities: set[str] = set()
    if not role_codes:
        return capabilities

    for role_code in role_codes:
        capabilities.update(ROLE_CAPABILITIES.get(role_code, set()))

    docs = _db()["role_capabilities"].find(
        {
            "role_code": {"$in": list(role_codes)},
            "status": {"$in": ["active", "enabled", ""]},
        }
    )
    for doc in docs:
        capability_code = _normalize_value(doc.get("capability_code"))
        if capability_code:
            capabilities.add(capability_code)

    return capabilities


def _collect_permissions_for_roles(role_codes: set[str], capabilities: set[str]) -> set[str]:
    permissions: set[str] = set()
    for capability in capabilities:
        permissions.update(CAPABILITY_PERMISSIONS.get(capability, set()))
    if "*" in capabilities:
        permissions.add("*")
    if not role_codes:
        return permissions

    for role_code in role_codes:
        permissions.update(ROLE_PERMISSION_MAP.get(role_code, set()))

    docs = _db()["role_permissions"].find(
        {
            "role_code": {"$in": list(role_codes)},
            "status": {"$in": ["active", "enabled", ""]},
        }
    )
    for doc in docs:
        permission_code = _normalize_value(doc.get("permission_code"))
        if permission_code:
            permissions.add(permission_code)

    return permissions


def _resolve_project_scope(user: dict[str, Any], project_id: str | None = None) -> dict[str, Any]:
    db = _db()
    projects = db["projects"]

    if project_id:
        project = None
        if ObjectId.is_valid(project_id):
            project = projects.find_one({"_id": ObjectId(project_id)})
        if project is None:
            project = projects.find_one({"id": project_id})
        if project is None:
            return {"project_id": project_id, "accessible": False}

        access_snapshot = get_project_access_snapshot(
            project,
            user_id=_current_user_id(user),
            email=_current_user_email(user),
        )
        return {
            "project_id": str(project.get("_id")),
            "accessible": bool(
                has_internal_admin_access(user) or access_snapshot.get("accessible")
            ),
            "owner_user_id": access_snapshot.get("owner_user_id"),
            "owner_email": access_snapshot.get("owner_email"),
            "access_via": access_snapshot.get("via"),
            "member_role": access_snapshot.get("member_role"),
        }

    if has_internal_admin_access(user):
        return {"scope": "all", "project_count": int(projects.count_documents({}))}

    user_id = _current_user_id(user)
    user_email = _current_user_email(user)
    project_ids = set(list_accessible_project_ids(user_id=user_id, email=user_email))

    filters: list[dict[str, Any]] = []
    if user_id:
        filters.append({"owner_user_id": user_id})
    if user_email:
        filters.append({"owner_email": user_email})

    if filters:
        docs = projects.find({"$or": filters}, {"_id": 1})
        project_ids.update(str(doc.get("_id")) for doc in docs if doc.get("_id") is not None)

    if not project_ids:
        return {"scope": "owned", "project_ids": []}

    return {"scope": "owned", "project_ids": sorted(project_ids)}


def _resolve_workflow_state(project_id: str | None) -> dict[str, Any]:
    if not project_id:
        return {"state": None, "phase": None}

    db = _db()
    projects = db["projects"]
    project = None
    if ObjectId.is_valid(project_id):
        project = projects.find_one({"_id": ObjectId(project_id)})
    if project is None:
        return {"state": None, "phase": None}

    project_id_value = str(project.get("_id"))
    workflow_query: dict[str, Any] = {"project_id": project_id_value}
    if ObjectId.is_valid(project_id_value):
        workflow_query = {"project_id": {"$in": [project_id_value, ObjectId(project_id_value)]}}
    latest_event = db["workflow_events"].find_one(workflow_query, sort=[("created_at", -1)])
    return {
        "state": _normalize_value(project.get("status")) or None,
        "phase": _normalize_value(project.get("phase")) or None,
        "latest_transition": {
            "from_state": _normalize_value((latest_event or {}).get("from_state")) or None,
            "to_state": _normalize_value((latest_event or {}).get("to_state")) or None,
            "created_at": (latest_event or {}).get("created_at"),
        } if latest_event else None,
    }


def resolve_access_context(
    user_id: str,
    project_id: str | None = None,
    *,
    user_email: str = "",
) -> dict[str, Any]:
    user = _load_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found for access context.",
        )

    role_codes = _collect_role_codes_for_user(user)
    capabilities = _collect_capabilities_for_roles(role_codes)
    permissions = _collect_permissions_for_roles(role_codes, capabilities)

    entitlements = list_user_project_entitlements(
        user_id,
        email=user_email or _current_user_email(user),
        active_only=True,
    )
    if project_id:
        entitlements = [
            entitlement
            for entitlement in entitlements
            if _normalize_value(entitlement.get("project_id")) == _normalize_value(project_id)
        ]

    normalized_project_id = _normalize_value(project_id)
    return {
        "role_codes": sorted(role_codes),
        "capabilities": sorted(capabilities),
        "permissions": sorted(permissions),
        "entitlements": entitlements,
        "project_scope": _resolve_project_scope(user, project_id),
        "workflow_state": _resolve_workflow_state(project_id),
        "project_id": normalized_project_id or None,
    }


def _get_or_resolve_access_context(
    current_user: dict[str, Any],
    *,
    project_id: str | None,
) -> dict[str, Any]:
    normalized_project_id = _normalize_value(project_id) or None
    cached_context = current_user.get("_access_context")
    if isinstance(cached_context, dict):
        cached_project_id = _normalize_value(cached_context.get("project_id")) or None
        if cached_project_id == normalized_project_id:
            return cached_context

    user_id = _current_user_id(current_user)
    user_email = _current_user_email(current_user)
    if user_email:
        context = resolve_access_context(
            user_id,
            project_id=normalized_project_id,
            user_email=user_email,
        )
    else:
        context = resolve_access_context(
            user_id,
            project_id=normalized_project_id,
        )
    current_user["_access_context"] = context
    return context


def require_permission(permission_code: str):
    normalized_permission = _normalize_value(permission_code)
    if not normalized_permission:
        raise ValueError("permission_code is required.")

    def _dependency(
        request: Request,
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        context = _get_or_resolve_access_context(
            current_user,
            project_id=_extract_project_id_from_request(request),
        )
        permissions = set(context.get("permissions") or [])
        if "*" not in permissions and normalized_permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{normalized_permission}' is required.",
            )
        return current_user

    return _dependency


def require_any_permission(permission_codes: list[str]):
    normalized_permissions = [
        _normalize_value(code) for code in permission_codes if _normalize_value(code)
    ]
    if not normalized_permissions:
        raise ValueError("At least one permission code is required.")

    def _dependency(
        request: Request,
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        context = _get_or_resolve_access_context(
            current_user,
            project_id=_extract_project_id_from_request(request),
        )
        permissions = set(context.get("permissions") or [])
        if "*" not in permissions and not any(
            code in permissions for code in normalized_permissions
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="At least one required permission is missing.",
            )
        return current_user

    return _dependency


def require_capability(capability_code: str):
    normalized_capability = _normalize_value(capability_code)
    if not normalized_capability:
        raise ValueError("capability_code is required.")

    def _dependency(
        request: Request,
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        context = _get_or_resolve_access_context(
            current_user,
            project_id=_extract_project_id_from_request(request),
        )
        capabilities = set(context.get("capabilities") or [])
        if "*" not in capabilities and normalized_capability not in capabilities:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Capability '{normalized_capability}' is required.",
            )
        return current_user

    return _dependency


def require_entitlement(
    capability: str,
    *,
    allow_internal_admin: bool = False,
):
    normalized_capability = _normalize_value(capability)
    if not normalized_capability:
        raise ValueError("capability is required.")

    def _dependency(
        request: Request,
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        if has_internal_admin_access(current_user):
            if allow_internal_admin:
                return current_user
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Customer package entitlement is required.",
            )

        project_id, family_id, member_id = _extract_workspace_identifiers(request)

        from app.services.workspace_access_service import resolve_workspace_context

        context = resolve_workspace_context(
            current_user,
            project_id=project_id,
            family_id=family_id,
            member_id=member_id,
        )
        entitlements = context.get("resolved_entitlements") or {}
        if not bool(entitlements.get(normalized_capability)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Entitlement '{normalized_capability}' is required.",
            )
        current_user["_workspace_context"] = context
        return current_user

    return _dependency


def enforce_limit(
    limit_type: str,
    value: int | float,
    *,
    context: dict[str, Any],
) -> None:
    normalized_limit = _normalize_value(limit_type)
    entitlements = context.get("resolved_entitlements") or {}

    if normalized_limit == "uploads":
        max_allowed = int(entitlements.get("max_uploads") or 0)
    elif normalized_limit == "family_members":
        max_allowed = int(entitlements.get("max_members") or 0)
    elif normalized_limit == "vault_storage_bytes":
        max_allowed = int(float(entitlements.get("max_storage_gb") or 0) * BYTES_PER_GB)
    else:
        raise ValueError(f"Unsupported limit type: {limit_type}")

    if max_allowed <= 0:
        return

    if float(value) > float(max_allowed):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Limit exceeded for '{normalized_limit}'.",
        )


def transition_project(
    project_id: str,
    to_state: str,
    actor: dict[str, Any] | str,
) -> dict[str, Any]:
    db = _db()
    projects = db["projects"]

    if not ObjectId.is_valid(project_id):
        raise HTTPException(status_code=400, detail="Invalid project id.")

    project = projects.find_one({"_id": ObjectId(project_id)})
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    from_state = _normalize_value(project.get("status"))
    target_state = _normalize_value(to_state)
    if not target_state:
        raise HTTPException(status_code=400, detail="to_state is required.")

    allowed_transitions = sorted(WORKFLOW_ALLOWED_TRANSITIONS.get(from_state, set()))
    if target_state not in set(allowed_transitions):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Invalid transition from '{from_state or 'unknown'}' to '{target_state}'. "
                f"Allowed transitions: {allowed_transitions}."
            ),
        )

    actor_user_id = ""
    actor_email = ""
    actor_name = ""
    if isinstance(actor, dict):
        actor_user_id = _normalize_value(
            actor.get("id") or actor.get("_id") or actor.get("user_id")
        )
        actor_email = _normalize_value(actor.get("email"))
        actor_name = _normalize_value(actor.get("full_name") or actor.get("name"))
    else:
        actor_user_id = _normalize_value(actor)

    if not actor_user_id:
        raise HTTPException(status_code=400, detail="Actor user id is required.")

    if actor_email:
        access_context = resolve_access_context(
            actor_user_id,
            project_id=project_id,
            user_email=actor_email,
        )
    else:
        access_context = resolve_access_context(
            actor_user_id,
            project_id=project_id,
        )
    permission_pool = set(access_context.get("permissions") or [])
    required_permissions = {
        "project.workflow.transition",
        f"project.workflow.transition.{target_state}",
    }
    if "*" not in permission_pool and permission_pool.isdisjoint(required_permissions):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Actor is not permitted to transition this project.",
        )

    next_phase = WORKFLOW_PHASE_BY_STATE.get(target_state, _normalize_value(project.get("phase")))
    now = datetime.now(timezone.utc)
    projects.update_one(
        {"_id": ObjectId(project_id)},
        {
            "$set": {
                "status": target_state,
                "phase": next_phase,
                "updated_at": now,
            }
        },
    )
    updated_project = projects.find_one({"_id": ObjectId(project_id)}) or project

    role_codes = access_context.get("role_codes") or []
    create_workflow_event(
        project_id=project_id,
        from_state=from_state,
        to_state=target_state,
        status="recorded",
        actor_user_id=actor_user_id,
        actor_role_code=str(role_codes[0] if role_codes else ""),
        context={"phase": next_phase},
    )
    write_audit_log(
        actor_user_id=actor_user_id or None,
        actor_email=actor_email or None,
        actor_name=actor_name or None,
        action="project_workflow_transition",
        target_type="project",
        target_id=project_id,
        before={"status": from_state, "phase": _normalize_value(project.get("phase"))},
        after={"status": target_state, "phase": next_phase},
        context={"required_permissions": sorted(required_permissions)},
        result="success",
    )
    return updated_project
