from fastapi import APIRouter, HTTPException, status

from app.services.issued_certificate_service import IssuedCertificateService

router = APIRouter(
    prefix="/certificate-versions",
    tags=["Certificate Versions"],
)

service = IssuedCertificateService()


@router.get("/family/{family_id}")
def list_family_certificate_versions(family_id: str):
    try:
        return service.list_family_certificate_versions(family_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list family certificate versions: {str(exc)}",
        ) from exc


@router.get("/family/{family_id}/latest")
def get_latest_family_certificate(family_id: str):
    try:
        return service.get_latest_family_certificate(family_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch latest family certificate: {str(exc)}",
        ) from exc


@router.post("/ensure-indexes")
def ensure_certificate_indexes():
    try:
        return service.ensure_indexes()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ensure certificate indexes: {str(exc)}",
        ) from exc