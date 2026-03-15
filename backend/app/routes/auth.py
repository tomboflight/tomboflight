from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.auth_service import authenticate_user, build_user_response, register_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: UserCreate):
    user = register_user(payload)
    if user is None:
        raise HTTPException(status_code=400, detail="Email already registered.")
    return build_user_response(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin):
    token = authenticate_user(payload.email, payload.password)
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(current_user: dict = Depends(get_current_user)):
    return build_user_response(current_user)