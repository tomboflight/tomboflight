from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import get_database
from app.dependencies.auth import (
    get_current_user,
    has_internal_admin_access,
    require_package_capability,
)
from app.services.issued_certificate_service import IssuedCertificateService
from app.services.workspace_access_service import family_is_visible_to_user

router = APIRouter(
    prefix="/issued-certificates",
    tags=["Issued Certificates"],
)

service = IssuedCertificateService()


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


def _require_family_access(
    family_id: str,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    db = get_database()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database is not connected.",
        )

    if not family_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="family_id is required.",
        )

    if not ObjectId.is_valid(family_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid family id.",
        )

    family = db["families"].find_one({"_id": ObjectId(family_id)})
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found.",
        )

    if has_internal_admin_access(current_user):
        return family

    current_user_id = _current_user_id(current_user)
    current_user_email = _current_user_email(current_user)
    current_user_name = _current_user_display_name(current_user)

    if not family_is_visible_to_user(
        family=family,
        current_user_id=current_user_id,
        current_user_email=current_user_email,
        current_user_name=current_user_name,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this family certificate.",
        )

    return family


def _extract_family_id_from_record(record: dict[str, Any]) -> str | None:
    direct = record.get("family_id")
    if direct:
        return str(direct)

    certificate = record.get("certificate") or {}
    family = certificate.get("family") or {}

    nested_id = family.get("id") or family.get("family_id")
    if nested_id:
        return str(nested_id)

    return None


@router.post("/issue/{family_id}")
def issue_certificate(
    family_id: str,
    notes: str | None = Query(default=None),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    require_package_capability(
        current_user,
        "can_use_lineage_certificate",
        detail="Your active package does not include lineage certificates.",
    )
    _require_family_access(family_id, current_user)

    issued_by = (
        current_user.get("email")
        or current_user.get("username")
        or current_user.get("full_name")
        or current_user.get("name")
        or current_user.get("id")
        or "system"
    )

    try:
        return service.issue_certificate(
            family_id=family_id,
            issued_by=str(issued_by),
            notes=notes,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to issue certificate: {str(exc)}",
        ) from exc


@router.get("/")
def list_issued_certificates(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    require_package_capability(
        current_user,
        "can_use_lineage_certificate",
        detail="Your active package does not include lineage certificates.",
    )
    try:
        records = service.list_certificates(limit=limit)
        issued_records = []

        if isinstance(records, dict):
            payload_records = records.get("issued_certificates")
            if isinstance(payload_records, list):
                issued_records = payload_records
        elif isinstance(records, list):
            issued_records = records

        if has_internal_admin_access(current_user):
            if isinstance(records, dict):
                return records

            return {
                "success": True,
                "count": len(issued_records),
                "issued_certificates": issued_records,
            }

        visible_records = []
        for record in issued_records:
            if not isinstance(record, dict):
                continue

            family_id = _extract_family_id_from_record(record)
            if not family_id:
                continue

            try:
                _require_family_access(family_id, current_user)
                visible_records.append(record)
            except HTTPException:
                continue

        return {
            "success": True,
            "count": len(visible_records),
            "issued_certificates": visible_records,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list issued certificates: {str(exc)}",
        ) from exc


@router.get("/by-certificate-id/{certificate_id}")
def get_issued_certificate_by_certificate_id(
    certificate_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    require_package_capability(
        current_user,
        "can_use_lineage_certificate",
        detail="Your active package does not include lineage certificates.",
    )
    try:
        record = service.get_certificate_by_certificate_id(certificate_id)
        family_id = _extract_family_id_from_record(record)
        if not family_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Certificate family could not be resolved.",
            )

        _require_family_access(family_id, current_user)
        return record
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch issued certificate: {str(exc)}",
        ) from exc


@router.get("/{record_id}")
def get_issued_certificate(
    record_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    require_package_capability(
        current_user,
        "can_use_lineage_certificate",
        detail="Your active package does not include lineage certificates.",
    )
    try:
        record = service.get_certificate_by_record_id(record_id)
        family_id = _extract_family_id_from_record(record)
        if not family_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Certificate family could not be resolved.",
            )

        _require_family_access(family_id, current_user)
        return record
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch issued certificate: {str(exc)}",
        ) from exc
