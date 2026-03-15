from fastapi import APIRouter

from app.schemas.user import UserCreate, UserResponse, build_user_response
from app.services.user_service import create_user, list_users

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=list[UserResponse])
def get_users():
    users = list_users()
    return [build_user_response(user) for user in users]


@router.post("/", response_model=UserResponse)
def create_user_route(payload: UserCreate):
    user = create_user(payload)
    return build_user_response(user)
