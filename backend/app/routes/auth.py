from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.config import settings
from app.dependencies.auth import COOKIE_NAME, get_current_user
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.auth_service import authenticate_user, build_user_response, register_user

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