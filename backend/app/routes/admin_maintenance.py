import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import require_permission
from app.schemas.db_bootstrap import (
    DropLegacyIndexesResponse,
    ProjectMembersBackfillResponse,
    WorkspaceAnchorBackfillResponse,
)
from app.services.db_bootstrap_service import drop_legacy_indexes
from app.services.project_membership_service import backfill_all_project_members
from app.services.viewer_manifest_service import (
    ensure_project_workspace_anchor,
    load_project_workspace_anchor,
)
from app.database import get_database

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/maintenance",
    tags=["Admin Maintenance"],
)


@router.post(
    "/drop-legacy-indexes",
    response_model=DropLegacyIndexesResponse,
)
def run_drop_legacy_indexes(
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    try:
        return drop_legacy_indexes()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Legacy index cleanup failed: {exc}",
        ) from exc


@router.post(
    "/backfill-project-members",
    response_model=ProjectMembersBackfillResponse,
)
def run_backfill_project_members(
    limit: int = Query(default=500, ge=1, le=5000),
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    try:
        result = backfill_all_project_members(limit=limit)
        return ProjectMembersBackfillResponse(
            message="Project members backfill completed.",
            scanned=result["scanned"],
            backfilled=result["backfilled"],
            already_present=result["already_present"],
            skipped=result["skipped"],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Project members backfill failed: {exc}",
        ) from exc


@router.post(
    "/backfill-workspace-anchors",
    response_model=WorkspaceAnchorBackfillResponse,
)
def run_backfill_workspace_anchors(
    limit: int = Query(default=100, ge=1, le=1000),
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    del current_user
    db = get_database()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database is not connected.",
        )

    scanned = 0
    provisioned = 0
    already_present = 0
    skipped = 0

    try:
        cursor = db["projects"].find({}).limit(max(1, min(limit, 1000)))
        for project in cursor:
            scanned += 1

            project_lane = str(project.get("project_lane") or project.get("package_lane") or "").strip()
            if project_lane not in {"portrait", "household", "network", "organization"}:
                skipped += 1
                continue

            family_doc, _primary_member, _project = load_project_workspace_anchor(
                project=project,
            )
            if family_doc is not None:
                already_present += 1
                continue

            try:
                family_doc_after, _member_after, _proj_after = ensure_project_workspace_anchor(
                    project=project,
                )
                if family_doc_after is not None:
                    provisioned += 1
                else:
                    skipped += 1
            except Exception as exc:
                project_id_str = str(project.get("_id", ""))
                logger.warning(
                    "workspace anchor backfill failed for project %s: %s",
                    project_id_str,
                    exc,
                )
                skipped += 1

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workspace anchor backfill failed: {exc}",
        ) from exc

    return WorkspaceAnchorBackfillResponse(
        message="Workspace anchor backfill completed.",
        scanned=scanned,
        provisioned=provisioned,
        already_present=already_present,
        skipped=skipped,
    )
