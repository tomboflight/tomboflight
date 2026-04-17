from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.config import settings
from app.core.security import create_csrf_token, decode_access_token
from app.dependencies.auth import COOKIE_NAME, get_current_user, require_capability
from app.schemas.auth import (
    MfaDisableRequest,
    MfaEnrollmentBeginRequest,
    MfaEnrollmentVerifyRequest,
    MfaLoginVerifyRequest,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.services.auth_service import (
    admin_reset_user_security,
    admin_issue_password_reset,
    authenticate_user,
    begin_mfa_enrollment,
    begin_mfa_enrollment_for_user,
    build_user_response,
    change_password,
    disable_mfa_for_user,
    get_user_by_id,
    register_user,
    request_password_reset,
    reset_password_with_token,
    verify_mfa_enrollment,
    verify_mfa_login_challenge,
)
from app.services.access_context_service import build_access_context
from app.services.rate_limit_service import (
    clear_failures,
    enforce_lockout,
    enforce_rate_limit,
    record_failure,
)
from app.services.audit_log_service import create_audit_log

router = APIRouter(prefix="/auth", tags=["Authentication"])

SameSiteMode = Literal["lax", "strict", "none"]
COOKIE_MAX_AGE_SECONDS = int(settings.access_token_expire_minutes or 60) * 60
CSRF_COOKIE_NAME = "tol_csrf_token"


def _is_secure_request(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto.lower() == "https":
        return True
    return request.url.scheme == "https"


def _cookie_samesite(request: Request) -> SameSiteMode:
    return "none" if _is_secure_request(request) else "lax"


def _apply_no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Content-Type-Options"] = "nosniff"


def _set_auth_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_is_secure_request(request),
        samesite=_cookie_samesite(request),
        path="/",
        max_age=COOKIE_MAX_AGE_SECONDS,
    )


def _set_csrf_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=_is_secure_request(request),
        samesite=_cookie_samesite(request),
        path="/",
        max_age=max(60, int(settings.csrf_token_expire_minutes or 120) * 60),
    )


def _clear_auth_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        samesite=_cookie_samesite(request),
        secure=_is_secure_request(request),
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path="/",
        samesite=_cookie_samesite(request),
        secure=_is_secure_request(request),
    )


def _rate_key_from_request(request: Request, *, principal: str = "") -> str:
    forwarded_for = str(request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    client_host = str((request.client.host if request.client else "") or "").strip()
    base = forwarded_for or client_host or "unknown"
    normalized_principal = str(principal or "").strip().lower()
    return f"{base}:{normalized_principal}" if normalized_principal else base


def _enforce_rate_limit_with_audit(
    *,
    scope: str,
    key: str,
    limit: int,
    window_seconds: int,
    audit_action: str,
) -> None:
    try:
        enforce_rate_limit(
            scope=scope,
            key=key,
            limit=limit,
            window_seconds=window_seconds,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            try:
                create_audit_log(audit_action, None, "auth", key, {"scope": scope})
            except Exception:
                pass
        raise


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate, response: Response):
    try:
        user = register_user(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if user is None:
        raise HTTPException(status_code=400, detail="Email already registered.")

    _apply_no_store(response)
    return build_user_response(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, request: Request, response: Response):
    login_scope_key = _rate_key_from_request(request, principal=payload.email)
    _enforce_rate_limit_with_audit(
        scope="auth_login",
        key=login_scope_key,
        limit=max(1, int(settings.auth_login_rate_limit or 10)),
        window_seconds=max(1, int(settings.auth_rate_limit_window_seconds or 60)),
        audit_action="login_throttled",
    )
    enforce_lockout(scope="auth_login_failures", key=login_scope_key)
    login_result = authenticate_user(payload.email, payload.password)
    if login_result is None:
        locked = record_failure(
            scope="auth_login_failures",
            key=login_scope_key,
            lockout_threshold=max(1, int(settings.auth_failure_lockout_threshold or 5)),
            lockout_seconds=max(1, int(settings.auth_failure_lockout_seconds or 300)),
        )
        if locked:
            try:
                create_audit_log(
                    "login_lockout_triggered",
                    None,
                    "user",
                    payload.email.lower(),
                    {"email": payload.email.lower()},
                )
            except Exception:
                pass
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    clear_failures(scope="auth_login_failures", key=login_scope_key)
    if login_result.get("status") == "mfa_required":
        return TokenResponse(
            access_token="",
            mfa_required=True,
            mfa_challenge_token=str(login_result.get("mfa_challenge_token") or ""),
        )
    if login_result.get("status") == "mfa_enrollment_required":
        return TokenResponse(
            access_token="",
            mfa_required=True,
            mfa_enrollment_required=True,
            mfa_challenge_token=str(login_result.get("mfa_challenge_token") or ""),
        )

    token = str(login_result.get("access_token") or "")
    _set_auth_cookie(response, request, token)
    csrf_token = create_csrf_token(
        _extract_user_id_from_token(token),
        ttl_minutes=max(1, int(settings.csrf_token_expire_minutes or 120)),
    )
    _set_csrf_cookie(response, request, csrf_token)
    _apply_no_store(response)

    return TokenResponse(access_token=token, csrf_token=csrf_token)


@router.post("/logout")
def logout(request: Request, response: Response):
    _clear_auth_cookie(response, request)
    _apply_no_store(response)
    return {"success": True, "message": "Logged out successfully."}


@router.get("/csrf-token")
def issue_csrf_token(request: Request, response: Response, current_user: dict = Depends(get_current_user)):
    user_id = _current_user_id(current_user)
    csrf_token = create_csrf_token(
        user_id,
        ttl_minutes=max(1, int(settings.csrf_token_expire_minutes or 120)),
    )
    _set_csrf_cookie(response, request, csrf_token)
    _apply_no_store(response)
    return {"csrf_token": csrf_token}


@router.post("/mfa/enroll/begin")
def mfa_enroll_begin(payload: MfaEnrollmentBeginRequest, response: Response):
    try:
        result = begin_mfa_enrollment(payload.mfa_challenge_token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _apply_no_store(response)
    return result


@router.post("/mfa/enroll/begin-session")
def mfa_enroll_begin_session(
    response: Response,
    current_user: dict = Depends(get_current_user),
):
    user = get_user_by_id(_current_user_id(current_user))
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")
    try:
        result = begin_mfa_enrollment_for_user(user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _apply_no_store(response)
    return result


@router.post("/mfa/enroll/verify", response_model=TokenResponse)
def mfa_enroll_verify(
    payload: MfaEnrollmentVerifyRequest,
    request: Request,
    response: Response,
):
    rate_key = _rate_key_from_request(request)
    _enforce_rate_limit_with_audit(
        scope="auth_mfa_verify",
        key=rate_key,
        limit=max(1, int(settings.auth_mfa_verify_rate_limit or 10)),
        window_seconds=max(1, int(settings.auth_rate_limit_window_seconds or 60)),
        audit_action="mfa_verify_throttled",
    )
    enforce_lockout(scope="auth_mfa_failures", key=rate_key)
    try:
        result = verify_mfa_enrollment(payload.setup_token, payload.code)
    except ValueError as exc:
        locked = record_failure(
            scope="auth_mfa_failures",
            key=rate_key,
            lockout_threshold=max(1, int(settings.auth_failure_lockout_threshold or 5)),
            lockout_seconds=max(1, int(settings.auth_failure_lockout_seconds or 300)),
        )
        if locked:
            try:
                create_audit_log("mfa_failure_lockout", None, "auth", "mfa", {"reason": "enrollment_verify"})
            except Exception:
                pass
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    clear_failures(scope="auth_mfa_failures", key=rate_key)
    token = str(result.get("access_token") or "")
    _set_auth_cookie(response, request, token)
    user_csrf = create_csrf_token(
        _extract_user_id_from_token(token),
        ttl_minutes=max(1, int(settings.csrf_token_expire_minutes or 120)),
    )
    _set_csrf_cookie(response, request, user_csrf)
    _apply_no_store(response)
    return TokenResponse(
        access_token=token,
        csrf_token=user_csrf,
        backup_codes=list(result.get("backup_codes") or []),
    )


def _extract_user_id_from_token(token: str) -> str:
    payload = decode_access_token(token) or {}
    return str(payload.get("user_id") or payload.get("sub") or "").strip()


@router.post("/mfa/login/verify", response_model=TokenResponse)
def mfa_login_verify(
    payload: MfaLoginVerifyRequest,
    request: Request,
    response: Response,
):
    rate_key = _rate_key_from_request(request)
    _enforce_rate_limit_with_audit(
        scope="auth_mfa_verify",
        key=rate_key,
        limit=max(1, int(settings.auth_mfa_verify_rate_limit or 10)),
        window_seconds=max(1, int(settings.auth_rate_limit_window_seconds or 60)),
        audit_action="mfa_verify_throttled",
    )
    enforce_lockout(scope="auth_mfa_failures", key=rate_key)
    try:
        result = verify_mfa_login_challenge(
            payload.mfa_challenge_token,
            code=payload.code,
            recovery_code=payload.recovery_code,
        )
    except ValueError as exc:
        record_failure(
            scope="auth_mfa_failures",
            key=rate_key,
            lockout_threshold=max(1, int(settings.auth_failure_lockout_threshold or 5)),
            lockout_seconds=max(1, int(settings.auth_failure_lockout_seconds or 300)),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    clear_failures(scope="auth_mfa_failures", key=rate_key)
    token = str(result.get("access_token") or "")
    _set_auth_cookie(response, request, token)
    user_csrf = create_csrf_token(
        _extract_user_id_from_token(token),
        ttl_minutes=max(1, int(settings.csrf_token_expire_minutes or 120)),
    )
    _set_csrf_cookie(response, request, user_csrf)
    _apply_no_store(response)
    return TokenResponse(access_token=token, csrf_token=user_csrf)


@router.post("/mfa/disable")
def mfa_disable(
    payload: MfaDisableRequest,
    response: Response,
    current_user: dict = Depends(get_current_user),
):
    user = get_user_by_id(_current_user_id(current_user))
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")
    try:
        disable_mfa_for_user(
            user=user,
            current_password=payload.current_password,
            code=payload.code,
            recovery_code=payload.recovery_code,
            actor_user_id=_current_user_id(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _apply_no_store(response)
    return {"success": True, "message": "MFA disabled successfully."}


@router.get("/me", response_model=UserResponse)
def me(response: Response, current_user: dict = Depends(get_current_user)):
    _apply_no_store(response)
    payload = build_user_response(current_user)
    try:
        context = build_access_context(current_user)
    except Exception:
        context = {}
    payload["active_project_id"] = context.get("active_project_id")
    payload["active_family_id"] = context.get("active_family_id")
    return payload


def _current_user_id(user: dict) -> str:
    raw_value = user.get("id") or user.get("_id") or user.get("user_id")
    return str(raw_value or "").strip()


def _current_user_display(user: dict) -> str:
    return (
        str(user.get("full_name") or user.get("name") or user.get("email") or "").strip()
        or "Tomb of Light Admin"
    )


@router.post("/password-reset/request", response_model=PasswordResetResponse)
def password_reset_request_route(payload: PasswordResetRequest, response: Response):
    _enforce_rate_limit_with_audit(
        scope="auth_password_reset_request",
        key=payload.email.lower(),
        limit=max(1, int(settings.auth_password_reset_request_rate_limit or 5)),
        window_seconds=max(1, int(settings.auth_rate_limit_window_seconds or 60)),
        audit_action="password_reset_request_throttled",
    )
    result = request_password_reset(payload.email)
    _apply_no_store(response)
    return result


@router.post("/password-reset/confirm", response_model=PasswordResetResponse)
def password_reset_confirm_route(
    payload: PasswordResetConfirm,
    request: Request,
    response: Response,
):
    confirm_scope_key = _rate_key_from_request(
        request,
        principal=payload.token[:16],
    )
    _enforce_rate_limit_with_audit(
        scope="auth_password_reset_confirm",
        key=confirm_scope_key,
        limit=max(1, int(settings.auth_password_reset_confirm_rate_limit or 10)),
        window_seconds=max(1, int(settings.auth_rate_limit_window_seconds or 60)),
        audit_action="password_reset_confirm_throttled",
    )
    try:
        result = reset_password_with_token(payload.token, payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _apply_no_store(response)
    return result


@router.post("/password-change", response_model=PasswordResetResponse)
def password_change_route(
    payload: PasswordChangeRequest,
    response: Response,
    current_user: dict = Depends(get_current_user),
):
    if payload.new_password != payload.confirm_new_password:
        raise HTTPException(status_code=400, detail="New passwords do not match.")

    try:
        result = change_password(
            _current_user_id(current_user),
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _apply_no_store(response)
    return result


@router.post(
    "/admin/users/{user_id}/password-reset",
    response_model=PasswordResetResponse,
)
def admin_issue_password_reset_route(
    user_id: str,
    response: Response,
    current_user: dict = Depends(require_capability("manage_users_full")),
):
    try:
        result = admin_issue_password_reset(
            user_id,
            admin_user_id=_current_user_id(current_user),
            admin_display=_current_user_display(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _apply_no_store(response)
    return result


@router.post("/admin/users/{user_id}/security-reset")
def admin_security_reset_route(
    user_id: str,
    response: Response,
    current_user: dict = Depends(require_capability("manage_users_full")),
):
    try:
        admin_reset_user_security(
            target_user_id=user_id,
            actor_user_id=_current_user_id(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _apply_no_store(response)
    return {"success": True, "message": "User sessions revoked and MFA reset."}
