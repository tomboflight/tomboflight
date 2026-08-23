from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.services.family_reunion_service import build_family_reunion_readiness
from app.services.workspace_access_service import resolve_workspace_context

router = APIRouter(prefix="/projects", tags=["Family Reunion Readiness"])


def _current_user_id(user: dict[str, Any]) -> str:
    value = user.get("id") or user.get("_id") or user.get("user_id")
    if value is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing.",
        )
    return str(value)


@router.get("/{project_id}/family-reunion-readiness")
def get_family_reunion_readiness(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    context = resolve_workspace_context(current_user, project_id=project_id)
    try:
        return build_family_reunion_readiness(
            project_id,
            _current_user_id(current_user),
            workspace_context=context,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

