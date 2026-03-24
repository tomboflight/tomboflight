from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.dependencies.auth import COOKIE_NAME, get_current_user
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.auth_service import authenticate_user, build_user_response, register_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


SameSiteMode = Literal["lax", "strict", "none"]


def _is_secure_request(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto.lower() == "https":
        return True
    return request.url.scheme == "https"


def _cookie_samesite(request: Request) -> SameSiteMode:
    return "none" if _is_secure_request(request) else "lax"


def _set_auth_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_is_secure_request(request),
        samesite=_cookie_samesite(request),
        path="/",
    )


def _clear_auth_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        samesite=_cookie_samesite(request),
        secure=_is_secure_request(request),
    )


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate):
    user = register_user(payload)
    if user is None:
        raise HTTPException(status_code=400, detail="Email already registered.")
    return build_user_response(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, request: Request, response: Response):
    token = authenticate_user(payload.email, payload.password)
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    _set_auth_cookie(response, request, token)

    return TokenResponse(access_token=token)


@router.post("/logout")
def logout(request: Request, response: Response):
    _clear_auth_cookie(response, request)
    return {"success": True, "message": "Logged out successfully."}


@router.get("/me", response_model=UserResponse)
def me(current_user: dict = Depends(get_current_user)):
    return build_user_response(current_user)