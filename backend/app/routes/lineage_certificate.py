from fastapi import APIRouter, HTTPException, status

from app.services.lineage_certificate_service import LineageCertificateService

router = APIRouter(
    prefix="/lineage-certificate",
    tags=["Lineage Certificate"],
)

service = LineageCertificateService()


@router.get("/{family_id}")
def get_lineage_certificate(family_id: str):
    try:
        return service.build_certificate(family_id)
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