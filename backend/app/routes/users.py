from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user, require_capability, require_permission
from app.schemas.experience import UserProfileResponse, UserProfileUpdate
from app.schemas.user import UserCreate, UserResponse, build_user_response
from app.services.auth_service import get_user_by_id
from app.services.user_service import create_user, list_users, update_user_profile
from app.services.workspace_access_service import build_workspace_context_snapshot

router = APIRouter(prefix="/users", tags=["Users"])


def _current_user_id(user: dict[str, Any]) -> str:
    raw_id = user.get("id") or user.get("_id") or user.get("user_id")
    if raw_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing.",
        )
    return str(raw_id)


@router.get("/", response_model=list[UserResponse])
def get_users(current_user: dict[str, Any] = Depends(require_permission("admin.users.read"))):
    users = list_users()
    return [build_user_response(user) for user in users]


@router.post("/", response_model=UserResponse)
def create_user_route(
    payload: UserCreate,
    current_user: dict[str, Any] = Depends(require_capability("manage_users_full")),
):
    user = create_user(payload)
    return build_user_response(user)


@router.get("/me/profile", response_model=UserProfileResponse)
def get_my_profile(current_user: dict[str, Any] = Depends(get_current_user)):
    user_id = _current_user_id(current_user)
    user = get_user_by_id(user_id) or current_user
    return {
        "id": str(user.get("_id") or user.get("id") or user_id),
        "email": str(user.get("email") or current_user.get("email") or "").strip().lower(),
        "full_name": str(user.get("full_name") or current_user.get("full_name") or current_user.get("name") or "").strip(),
        "role": str(user.get("role") or current_user.get("role") or "user").strip(),
        "status": str(user.get("status") or current_user.get("status") or "active").strip(),
        "created_at": str(user.get("created_at") or current_user.get("created_at") or ""),
        "last_login_at": user.get("last_login_at") or current_user.get("last_login_at"),
        "policy_version": user.get("policy_version") or current_user.get("policy_version"),
        "legal_acceptance": {
            "policy_version": user.get("policy_version") or current_user.get("policy_version"),
            "terms_accepted_at": user.get("terms_accepted_at") or current_user.get("terms_accepted_at"),
            "privacy_accepted_at": user.get("privacy_accepted_at") or current_user.get("privacy_accepted_at"),
            "eligibility_attested_at": user.get("eligibility_attested_at") or current_user.get("eligibility_attested_at"),
        },
    }


@router.patch("/me/profile", response_model=UserProfileResponse)
def patch_my_profile(
    payload: UserProfileUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    try:
        updated_user = update_user_profile(user_id, full_name=payload.full_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if updated_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    return {
        "id": str(updated_user.get("_id") or user_id),
        "email": str(updated_user.get("email") or current_user.get("email") or "").strip().lower(),
        "full_name": str(updated_user.get("full_name") or payload.full_name).strip(),
        "role": str(updated_user.get("role") or current_user.get("role") or "user").strip(),
        "status": str(updated_user.get("status") or current_user.get("status") or "active").strip(),
        "created_at": str(updated_user.get("created_at") or current_user.get("created_at") or ""),
        "last_login_at": updated_user.get("last_login_at") or current_user.get("last_login_at"),
        "policy_version": updated_user.get("policy_version") or current_user.get("policy_version"),
        "legal_acceptance": {
            "policy_version": updated_user.get("policy_version") or current_user.get("policy_version"),
            "terms_accepted_at": updated_user.get("terms_accepted_at") or current_user.get("terms_accepted_at"),
            "privacy_accepted_at": updated_user.get("privacy_accepted_at") or current_user.get("privacy_accepted_at"),
            "eligibility_attested_at": updated_user.get("eligibility_attested_at") or current_user.get("eligibility_attested_at"),
        },
    }


@router.get("/me/workspace-context")
def get_my_workspace_context(
    project_id: str = "",
    family_id: str = "",
    current_user: dict[str, Any] = Depends(get_current_user),
):
    return build_workspace_context_snapshot(
        current_user,
        project_id=project_id,
        family_id=family_id,
    )


@router.get("/me/access-context")
def get_my_access_context(
    project_id: str = "",
    family_id: str = "",
    current_user: dict[str, Any] = Depends(get_current_user),
):
    return get_my_workspace_context(
        project_id=project_id,
        family_id=family_id,
        current_user=current_user,
    )
