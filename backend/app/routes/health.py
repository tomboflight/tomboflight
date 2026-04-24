from fastapi import APIRouter, Response, status

from app.database import get_service_state

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check(response: Response):
    service_state = get_service_state()
    response.status_code = (
        status.HTTP_200_OK
        if service_state["ready"]
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return {
        "status": service_state["service_mode"],
        "service": "Tomb of Light API",
        **service_state,
    }


@router.get("/health/live")
def liveness_check():
    service_state = get_service_state()
    return {
        "status": "ok",
        "service": "Tomb of Light API",
        "service_mode": service_state["service_mode"],
        "database_connected": service_state["database_connected"],
        "ready": service_state["ready"],
        "degraded_reasons": service_state["degraded_reasons"],
    }


@router.get("/health/ready")
def readiness_check(response: Response):
    service_state = get_service_state()
    response.status_code = (
        status.HTTP_200_OK
        if service_state["ready"]
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return {
        "status": "ok" if service_state["ready"] else "unavailable",
        "service": "Tomb of Light API",
        **service_state,
    }
