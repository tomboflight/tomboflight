from typing import Any

from fastapi import APIRouter, Depends

from app.dependencies.auth import require_admin
from app.schemas.user import UserCreate, UserResponse, build_user_response
from app.services.user_service import create_user, list_users

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=list[UserResponse])
def get_users(current_user: dict[str, Any] = Depends(require_admin)):
    users = list_users()
    return [build_user_response(user) for user in users]


@router.post("/", response_model=UserResponse)
def create_user_route(
    payload: UserCreate,
    current_user: dict[str, Any] = Depends(require_admin),
):
    user = create_user(payload)
    return build_user_response(user)
