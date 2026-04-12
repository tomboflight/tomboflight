from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.config import settings
from app.dependencies.auth import COOKIE_NAME, get_current_user, require_permission
from app.schemas.auth import (
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
    admin_issue_password_reset,
    authenticate_user,
    build_user_response,
    change_password,
    register_user,
    request_password_reset,
    reset_password_with_token,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

SameSiteMode = Literal["lax", "strict", "none"]
COOKIE_MAX_AGE_SECONDS = int(settings.access_token_expire_minutes or 60) * 60


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


def _clear_auth_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        samesite=_cookie_samesite(request),
        secure=_is_secure_request(request),
    )


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
    token = authenticate_user(payload.email, payload.password)
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    _set_auth_cookie(response, request, token)
    _apply_no_store(response)

    return TokenResponse(access_token=token)


@router.post("/logout")
def logout(request: Request, response: Response):
    _clear_auth_cookie(response, request)
    _apply_no_store(response)
    return {"success": True, "message": "Logged out successfully."}


@router.get("/me", response_model=UserResponse)
def me(response: Response, current_user: dict = Depends(get_current_user)):
    _apply_no_store(response)
    return build_user_response(current_user)


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
    result = request_password_reset(payload.email)
    _apply_no_store(response)
    return result


@router.post("/password-reset/confirm", response_model=PasswordResetResponse)
def password_reset_confirm_route(
    payload: PasswordResetConfirm,
    response: Response,
):
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
    current_user: dict = Depends(require_permission("admin.users.write")),
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
