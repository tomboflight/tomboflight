from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user, has_internal_admin_access
from app.schemas.project import ProjectCreate, ProjectResponse, build_project_response
from app.services.project_service import create_project, list_projects

router = APIRouter(prefix="/projects", tags=["Projects"])


def _current_user_id(user: dict[str, Any]) -> str:
    raw_id = user.get("id") or user.get("_id") or user.get("user_id")
    if raw_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing.",
        )
    return str(raw_id)


def _current_user_email(user: dict[str, Any]) -> str:
    raw_email = user.get("email")
    if not raw_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user email is missing.",
        )
    return str(raw_email).strip().lower()


def _is_admin(user: dict[str, Any]) -> bool:
    return has_internal_admin_access(user)


@router.get("", response_model=list[ProjectResponse], include_in_schema=False)
@router.get("/", response_model=list[ProjectResponse])
def get_projects(current_user: dict[str, Any] = Depends(get_current_user)):
    current_user_id = _current_user_id(current_user)
    current_user_email = _current_user_email(current_user)

    projects = list_projects(
        owner_user_id=current_user_id,
        owner_email=current_user_email,
        is_admin=_is_admin(current_user),
    )
    return [build_project_response(project) for project in projects]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_route(
    payload: ProjectCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    current_user_id = _current_user_id(current_user)
    current_user_email = _current_user_email(current_user)

    if not _is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Projects are provisioned through paid packages and approved "
                "intake. Customer accounts cannot create projects directly."
            ),
        )

    project = create_project(payload)
    return build_project_response(project)
