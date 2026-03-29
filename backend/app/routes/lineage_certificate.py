from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_database
from app.dependencies.auth import (
    get_current_user,
)
from app.schemas.lineage_certificate import LineageCertificateResponse
from app.services.lineage_certificate_service import LineageCertificateService
from app.services.workspace_access_service import require_workspace_capability

router = APIRouter(
    prefix="/lineage-certificate",
    tags=["Lineage Certificate"],
)

service = LineageCertificateService()


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


def _current_user_display_name(user: dict[str, Any]) -> str:
    raw_name = user.get("full_name") or user.get("name") or ""
    return str(raw_name).strip()


@router.get("/{family_id}", response_model=LineageCertificateResponse)
def get_lineage_certificate(
    family_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    context = require_workspace_capability(
        current_user,
        family_id=family_id,
        capabilities=("can_use_lineage_certificate",),
        detail="Your active package does not include lineage certificates.",
    )
    resolved_family_id = str(context["family"].get("_id"))

    try:
        return service.build_certificate(resolved_family_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate lineage certificate: {str(exc)}",
        ) from exc
