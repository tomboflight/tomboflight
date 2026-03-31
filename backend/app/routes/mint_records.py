from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_database
from app.dependencies.auth import get_current_user, require_admin
from app.schemas.mint_record import (
    AdminMintApprovalPayload,
    CustomerMintApprovalPayload,
    PrepareMintRecordPayload,
)
from app.services.mint_job_service import queue_mint_pipeline, sync_receipt_for_mint_record
from app.services.mint_policy_service import describe_project_mint_eligibility
from app.services.mint_record_service import (
    approve_admin_mint_record,
    approve_customer_mint_record,
    build_mint_status,
    create_mint_record,
    ensure_mint_record_indexes,
    get_latest_mint_record,
    get_mint_record,
    list_mint_records,
)
from app.services.public_manifest_service import get_public_manifest_by_token_id
from app.services.workspace_access_service import resolve_workspace_context

router = APIRouter(tags=["Mint Records"])


def _normalize(value: Any) -> str:
    return str(value or "").strip()


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
    return _normalize(raw_email).lower()


def _project_context(
    current_user: dict[str, Any],
    project_id: str,
) -> dict[str, Any]:
    try:
        return resolve_workspace_context(current_user, project_id=project_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


def _project_for_request(current_user: dict[str, Any], project_id: str) -> dict[str, Any]:
    context = _project_context(current_user, project_id)
    project = context.get("project")
    if not isinstance(project, dict):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return project


def _require_project_match(project_id: str, mint_record_id: str) -> dict[str, Any]:
    record = get_mint_record(mint_record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mint record not found.",
        )
    if record["project_id"] != _normalize(project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mint record does not belong to the requested project.",
        )
    return record


def _admin_mint_overview_item(project: dict[str, Any]) -> dict[str, Any]:
    project_id = _normalize(project.get("_id") or project.get("id"))
    latest = get_latest_mint_record(project_id)
    status = build_mint_status(project_id)
    eligibility = describe_project_mint_eligibility(project)

    return {
        "project_id": project_id,
        "project_name": _normalize(project.get("project_name") or project.get("name")) or "Workspace",
        "owner_email": _normalize(project.get("owner_email")) or None,
        "package_code": _normalize(project.get("package_code") or project.get("package_slug")),
        "package_name": _normalize(project.get("package_name")) or None,
        "project_lane": _normalize(project.get("project_lane")) or None,
        "family_id": _normalize(project.get("family_id")) or None,
        "status": _normalize(project.get("status")) or None,
        "phase": _normalize(project.get("phase")) or None,
        "eligibility": eligibility,
        "latest_mint_record": latest,
        "mint_status": status,
    }


@router.on_event("startup")
def startup_mint_record_indexes():
    ensure_mint_record_indexes()


@router.get("/projects/{project_id}/mint-eligibility")
def get_project_mint_eligibility(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    project = _project_for_request(current_user, project_id)
    eligibility = describe_project_mint_eligibility(project)
    latest = get_latest_mint_record(project_id)
    eligibility["latest_mint_record_id"] = (latest or {}).get("id")
    eligibility["missing_approvals"] = list((latest or {}).get("pending_approvals") or [])
    return eligibility


@router.get("/admin/mint-records/overview")
def list_admin_mint_overview(
    limit: int = 100,
    search: str = "",
    status_filter: str = "",
    mintable_only: bool = False,
    current_user: dict[str, Any] = Depends(require_admin),
):
    del current_user

    db = get_database()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database is not connected.",
        )

    normalized_search = _normalize(search).lower()
    normalized_status = _normalize(status_filter).lower()

    projects = list(db["projects"].find({}).sort("updated_at", -1).limit(max(1, min(limit * 4, 1000))))
    items: list[dict[str, Any]] = []

    for project in projects:
        item = _admin_mint_overview_item(project)
        haystack = " ".join(
            [
                _normalize(item.get("project_id")),
                _normalize(item.get("project_name")),
                _normalize(item.get("owner_email")),
                _normalize(item.get("package_code")),
                _normalize(item.get("package_name")),
                _normalize(item.get("project_lane")),
            ]
        ).lower()

        if normalized_search and normalized_search not in haystack:
            continue

        latest_status = _normalize(((item.get("latest_mint_record") or {}).get("mint_status"))).lower()
        if normalized_status and latest_status != normalized_status:
            continue

        if mintable_only and not bool((item.get("eligibility") or {}).get("mint_policy", {}).get("product_includes_onchain_anchor")):
            continue

        items.append(item)
        if len(items) >= max(1, min(limit, 500)):
            break

    return {"items": items}


@router.post("/projects/{project_id}/mint-records/prepare")
def prepare_project_mint_record(
    project_id: str,
    payload: PrepareMintRecordPayload,
    current_user: dict[str, Any] = Depends(require_admin),
):
    _project_for_request(current_user, project_id)

    try:
        record = create_mint_record(
            project_id,
            version_strategy=payload.version_strategy,
            poster_style=payload.poster_style,
            public_title_opt_in=payload.public_title_opt_in,
            public_title=payload.public_title,
            public_title_kind=payload.public_title_kind,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "mint_record_id": record["id"],
        "version_number": record["version_number"],
        "status": record["mint_status"],
        "metadata_uri": record["metadata_uri"],
        "poster_image_uri_public": record["poster_image_uri_public"],
    }


@router.post("/projects/{project_id}/mint-records/{mint_record_id}/approve-admin")
def approve_project_mint_record_admin(
    project_id: str,
    mint_record_id: str,
    payload: AdminMintApprovalPayload,
    current_user: dict[str, Any] = Depends(require_admin),
):
    _project_for_request(current_user, project_id)
    _require_project_match(project_id, mint_record_id)

    try:
        return approve_admin_mint_record(
            mint_record_id,
            approved_by_email=_current_user_email(current_user),
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/projects/{project_id}/mint-records/{mint_record_id}/approve-customer")
def approve_project_mint_record_customer(
    project_id: str,
    mint_record_id: str,
    payload: CustomerMintApprovalPayload,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    _project_for_request(current_user, project_id)
    _require_project_match(project_id, mint_record_id)

    try:
        return approve_customer_mint_record(
            mint_record_id,
            approved_by_user_id=_current_user_id(current_user),
            approved_by_email=_current_user_email(current_user),
            notes=payload.notes,
            wallet_address=payload.wallet_address,
            approved_poster_opt_in=payload.approved_poster_opt_in,
            public_title_opt_in=payload.public_title_opt_in,
            public_title=payload.public_title,
            public_title_kind=payload.public_title_kind,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/projects/{project_id}/mint-records/{mint_record_id}/approve-customer-admin")
def approve_project_mint_record_customer_admin(
    project_id: str,
    mint_record_id: str,
    payload: CustomerMintApprovalPayload,
    current_user: dict[str, Any] = Depends(require_admin),
):
    _project_for_request(current_user, project_id)
    _require_project_match(project_id, mint_record_id)

    try:
        return approve_customer_mint_record(
            mint_record_id,
            approved_by_user_id=_current_user_id(current_user),
            approved_by_email=_current_user_email(current_user),
            notes=payload.notes or "Approved by internal admin override.",
            wallet_address=payload.wallet_address,
            approved_poster_opt_in=payload.approved_poster_opt_in,
            public_title_opt_in=payload.public_title_opt_in,
            public_title=payload.public_title,
            public_title_kind=payload.public_title_kind,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/projects/{project_id}/mint-records/{mint_record_id}/queue")
def queue_project_mint_record(
    project_id: str,
    mint_record_id: str,
    current_user: dict[str, Any] = Depends(require_admin),
):
    project = _project_for_request(current_user, project_id)
    _require_project_match(project_id, mint_record_id)

    eligibility = describe_project_mint_eligibility(project)
    if not eligibility.get("eligible"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This project is not ready to queue for minting yet: "
                + ", ".join(eligibility.get("reasons") or ["unknown_reason"])
            ),
        )

    try:
        return {
            "jobs": queue_mint_pipeline(
                project_id,
                mint_record_id,
                queued_by=_current_user_email(current_user),
            )
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/projects/{project_id}/mint-records")
def list_project_mint_records(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    _project_for_request(current_user, project_id)
    return {
        "items": list_mint_records(project_id),
    }


@router.get("/projects/{project_id}/mint-status")
def get_project_mint_status(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    _project_for_request(current_user, project_id)
    return build_mint_status(project_id)


@router.post("/mint-records/{mint_record_id}/sync")
def sync_project_mint_record(
    mint_record_id: str,
    current_user: dict[str, Any] = Depends(require_admin),
):
    del current_user

    try:
        return sync_receipt_for_mint_record(mint_record_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/tokens/{public_token_id}")
def get_public_token_landing_payload(public_token_id: str):
    manifest = get_public_manifest_by_token_id(public_token_id)
    if manifest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Public token record not found.",
        )
    if manifest["approval_status"] != "approved":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Public token record is not available yet.",
        )

    return {
        "public_token_id": manifest["public_token_id"],
        "metadata_uri": manifest["metadata_uri"],
        "project_id": manifest["project_id"],
        "version_number": manifest["version_number"],
        "poster_image_uri_public": manifest["poster_image_uri_public"],
        "approval_status": manifest["approval_status"],
        "payload": manifest["payload"],
    }
