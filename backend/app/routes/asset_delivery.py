from __future__ import annotations

from typing import Any
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse

from app.dependencies.auth import get_current_user
from app.services.mint_record_service import build_mint_status
from app.services.order_service import get_orders_for_user
from app.services.project_entitlement_service import get_project_entitlement
from app.services.workspace_access_service import resolve_workspace_context

router = APIRouter(tags=["Asset Delivery"])


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


def _project_for_request(
    current_user: dict[str, Any], project_id: str
) -> dict[str, Any]:
    try:
        context = resolve_workspace_context(current_user, project_id=project_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    project = context.get("project")
    if not isinstance(project, dict):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return project


def _resolve_order_for_project(
    current_user: dict[str, Any], project_id: str
) -> dict[str, Any] | None:
    """Return the most recent paid order associated with this project, or None."""
    try:
        orders = get_orders_for_user(current_user)
    except Exception:
        return None

    if not orders:
        return None

    # Prefer an order whose project_id field directly matches.
    for order in orders:
        order_project = _normalize(order.get("project_id"))
        if order_project and order_project == _normalize(project_id):
            return order

    # Fall back to the most recent paid package order for this user.
    paid_statuses = {"paid", "active", "fulfilled", "confirmed"}
    for order in orders:
        if _normalize(order.get("item_type")) == "package" and _normalize(
            order.get("status")
        ).lower() in paid_statuses:
            return order

    return orders[0] if orders else None


@router.get("/projects/{project_id}/digital-collectible")
def get_digital_collectible_delivery(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Returns the full digital collectible delivery payload for a project.

    Combines project entitlement, order, and mint status data so the
    front-end delivery page can render all live details in one request.
    """
    project = _project_for_request(current_user, project_id)

    project_doc_id = _normalize(project.get("_id") or project.get("id"))
    project_name = _normalize(
        project.get("project_name") or project.get("name")
    ) or "Your Workspace"
    created_at = project.get("created_at")

    # --- Entitlement ---
    entitlement = get_project_entitlement(project_doc_id) or {}
    package_code = _normalize(
        entitlement.get("package_code") or project.get("package_code") or ""
    )
    package_name = _normalize(
        entitlement.get("package_name") or entitlement.get("resolved_package_name") or ""
    )
    package_lane = _normalize(
        entitlement.get("package_lane") or project.get("project_lane") or ""
    )
    entitlement_status = _normalize(entitlement.get("status") or "")
    delivered_at = entitlement.get("delivered_at")
    maintenance_plan = _normalize(entitlement.get("maintenance_plan") or "")

    # --- Order ---
    order = _resolve_order_for_project(current_user, project_doc_id)
    order_id = _normalize((order or {}).get("id") or (order or {}).get("_id") or "")
    order_status = _normalize((order or {}).get("status") or "")
    order_created_at = (order or {}).get("created_at")
    order_package_name = _normalize((order or {}).get("package_name") or "")

    if not package_name and order_package_name:
        package_name = order_package_name

    # --- Mint Status ---
    try:
        mint_data = build_mint_status(project_doc_id)
    except Exception:
        mint_data = {}

    mint_enabled = bool(mint_data.get("mint_enabled"))
    mint_current_status = _normalize(
        mint_data.get("current_status") or mint_data.get("canonical_status") or ""
    )
    latest = mint_data.get("latest") or {}
    mint_record_id = _normalize(latest.get("mint_record_id") or "")
    chain = _normalize(latest.get("chain") or "")
    contract_address = _normalize(latest.get("contract_address") or "")
    token_id = _normalize(latest.get("token_id") or "")
    tx_hash = _normalize(latest.get("tx_hash") or "")
    public_token_id = _normalize(latest.get("public_token_id") or "")
    wallet = _normalize(latest.get("wallet") or latest.get("customer_wallet") or "")
    metadata_uri = _normalize(latest.get("metadata_uri") or "")
    poster_image_uri_public = _normalize(latest.get("poster_image_uri_public") or "")
    minted_at = latest.get("minted_at")
    version_number = latest.get("version_number")
    token_type = _normalize(latest.get("token_type") or "")

    # Determine what files / actions are currently available.
    has_poster = bool(poster_image_uri_public)
    has_metadata = bool(metadata_uri)
    is_minted = mint_current_status == "minted"
    is_mint_pending = mint_enabled and mint_current_status in {
        "pending",
        "queued",
        "approved",
        "minting",
        "pending_approval",
        "draft",
    }

    def _fmt_datetime(dt: Any) -> str | None:
        if dt is None:
            return None
        try:
            if hasattr(dt, "isoformat"):
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.isoformat()
            return str(dt)
        except Exception:
            return str(dt)

    return {
        # Project
        "project_id": project_doc_id,
        "project_name": project_name,
        "project_created_at": _fmt_datetime(created_at),
        # Package / Entitlement
        "package_code": package_code,
        "package_name": package_name,
        "package_lane": package_lane,
        "entitlement_status": entitlement_status,
        "delivered_at": _fmt_datetime(delivered_at),
        "maintenance_plan": maintenance_plan,
        # Order
        "order_id": order_id,
        "order_status": order_status,
        "order_created_at": _fmt_datetime(order_created_at),
        # Mint / NFT / Legacy Anchor
        "mint_enabled": mint_enabled,
        "mint_status": mint_current_status,
        "mint_record_id": mint_record_id,
        "chain": chain,
        "contract_address": contract_address,
        "token_id": token_id,
        "tx_hash": tx_hash,
        "public_token_id": public_token_id,
        "wallet": wallet,
        # Backward-compatible alias for consumers still reading customer_wallet.
        "customer_wallet": wallet,
        "minted_at": _fmt_datetime(minted_at),
        "version_number": version_number,
        "token_type": token_type,
        # Downloadable asset URIs
        "metadata_uri": metadata_uri,
        "poster_image_uri_public": poster_image_uri_public,
        # Availability flags
        "has_poster": has_poster,
        "has_metadata": has_metadata,
        "is_minted": is_minted,
        "is_mint_pending": is_mint_pending,
    }


@router.get("/projects/{project_id}/delivery/poster")
def download_delivery_poster(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> RedirectResponse:
    """
    Redirects the authenticated user to the public-safe poster image for their
    digital collectible.  Returns 404 when the poster is not yet available.
    """
    project = _project_for_request(current_user, project_id)
    project_doc_id = _normalize(project.get("_id") or project.get("id"))

    try:
        mint_data = build_mint_status(project_doc_id)
    except Exception:
        mint_data = {}

    latest = mint_data.get("latest") or {}
    poster_url = _normalize(latest.get("poster_image_uri_public") or "")

    if not poster_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Poster image is not yet available for this project.",
        )

    return RedirectResponse(url=poster_url, status_code=302)


@router.get("/projects/{project_id}/delivery/metadata")
def download_delivery_metadata(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> JSONResponse:
    """
    Returns the public metadata JSON for the digital collectible as a
    downloadable attachment.  Returns 404 when metadata is not yet available.
    """
    project = _project_for_request(current_user, project_id)
    project_doc_id = _normalize(project.get("_id") or project.get("id"))

    try:
        mint_data = build_mint_status(project_doc_id)
    except Exception:
        mint_data = {}

    latest = mint_data.get("latest") or {}
    metadata_uri = _normalize(latest.get("metadata_uri") or "")
    public_token_id = _normalize(latest.get("public_token_id") or "")

    if not metadata_uri:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metadata record is not yet available for this project.",
        )

    # Build a safe filename from the public token ID or fall back to project id.
    safe_name = (public_token_id or project_doc_id).replace("/", "_").replace(" ", "_")
    filename = f"{safe_name}-metadata.json"

    # Redirect clients to the canonical metadata URI with download headers.
    # We return the URI and metadata_uri rather than proxying the external file
    # to keep the backend stateless and avoid introducing an outbound HTTP call.
    content = {
        "metadata_uri": metadata_uri,
        "public_token_id": public_token_id,
        "project_id": project_doc_id,
    }

    return JSONResponse(
        content=content,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
