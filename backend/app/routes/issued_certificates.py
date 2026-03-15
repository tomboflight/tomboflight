from fastapi import APIRouter, HTTPException, Query, status

from app.services.issued_certificate_service import IssuedCertificateService

router = APIRouter(
    prefix="/issued-certificates",
    tags=["Issued Certificates"],
)

service = IssuedCertificateService()


@router.post("/issue/{family_id}")
def issue_certificate(
    family_id: str,
    issued_by: str = Query(default="system"),
    notes: str | None = Query(default=None),
):
    try:
        return service.issue_certificate(
            family_id=family_id,
            issued_by=issued_by,
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
def list_issued_certificates(limit: int = Query(default=50, ge=1, le=200)):
    try:
        return service.list_certificates(limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list issued certificates: {str(exc)}",
        ) from exc


@router.get("/{record_id}")
def get_issued_certificate(record_id: str):
    try:
        return service.get_certificate_by_record_id(record_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch issued certificate: {str(exc)}",
        ) from exc