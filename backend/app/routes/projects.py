from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_database

from app.dependencies.auth import (
    get_current_user,
    has_internal_admin_access,
    require_permission,
)
from app.schemas.experience import ExperienceLaneResponse
from app.schemas.project import ProjectCreate, ProjectResponse, build_project_response
from app.services.access_context_service import describe_project_experience_lane
from app.services.project_service import create_project, list_projects
from app.services.project_entitlement_service import get_project_entitlement

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


@router.get("", response_model=list[ProjectResponse], include_in_schema=False)
@router.get("/", response_model=list[ProjectResponse])
def get_projects(current_user: dict[str, Any] = Depends(get_current_user)):
    current_user_id = _current_user_id(current_user)
    current_user_email = _current_user_email(current_user)

    projects = list_projects(
        owner_user_id=current_user_id,
        owner_email=current_user_email,
        is_admin=has_internal_admin_access(current_user),
    )
    return [build_project_response(project) for project in projects]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_route(
    payload: ProjectCreate,
    current_user: dict[str, Any] = Depends(require_permission("projects.create")),
):
    del current_user
    project = create_project(payload)
    return build_project_response(project)


@router.get("/{project_id}/experience-lane", response_model=ExperienceLaneResponse)
def get_project_experience_lane(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        return describe_project_experience_lane(current_user, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{project_id}/limits")
def get_project_limits(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    current_user_id = _current_user_id(current_user)
    current_user_email = _current_user_email(current_user)

    projects = list_projects(
        owner_user_id=current_user_id,
        owner_email=current_user_email,
        is_admin=has_internal_admin_access(current_user),
    )
    if not any(str(project.get("id") or project.get("_id") or "") == project_id for project in projects):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    entitlement = get_project_entitlement(project_id)
    resolved = dict((entitlement or {}).get("resolved_entitlements") or {})

    db = get_database()
    uploads = list(db["uploaded_files"].find({"project_id": project_id, "quarantined": {"$ne": True}}))
    usage_upload_count = len(uploads)
    usage_storage_bytes = int(sum(int(item.get("size_bytes") or 0) for item in uploads))

    return {
        "project_id": project_id,
        "limits": {
            "max_uploads": resolved.get("max_uploads"),
            "max_storage_gb": resolved.get("max_storage_gb"),
            "max_members": resolved.get("max_members"),
            "max_households": resolved.get("max_households"),
            "max_org_nodes": resolved.get("max_org_nodes"),
        },
        "usage": {
            "uploads": usage_upload_count,
            "storage_bytes": usage_storage_bytes,
        },
    }
