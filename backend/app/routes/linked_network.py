from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.services.linked_network_service import build_linked_network
from app.services.workspace_access_service import require_workspace_capability

router = APIRouter(tags=["Linked Network"])


def _current_user_id(user: dict[str, Any]) -> str:
    raw_id = user.get("id") or user.get("_id") or user.get("user_id")
    if raw_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing.",
        )
    return str(raw_id)


@router.get("/projects/{project_id}/linked-network")
def get_linked_network(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    try:
        context = require_workspace_capability(
            current_user,
            project_id=project_id,
            capabilities=("can_link_households",),
            detail="Your package does not include linked household network access.",
        )
        return build_linked_network(
            project_id,
            user_id,
            workspace_context=context,
        )
    except HTTPException:
        raise
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
