from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user, require_any_package_capability
from app.services.viewer_manifest_service import build_viewer_manifest

router = APIRouter(prefix="/viewer", tags=["Viewer"])


@router.get("/manifest")
def get_viewer_manifest(
    project_id: str = Query(default=""),
    family_id: str = Query(default=""),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    require_any_package_capability(
        current_user,
        "can_use_viewer",
        "can_use_secure_share_viewer",
        detail="Your active package does not include viewer access.",
    )

    try:
        return build_viewer_manifest(
            current_user=current_user,
            project_id=project_id,
            family_id=family_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
