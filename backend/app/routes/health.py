from typing import Any

from fastapi import APIRouter, Depends, Response, status

from app.database import get_service_state
from app.dependencies.auth import require_super_admin

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


@router.get("/health/operational")
def operational_readiness_check(
    response: Response,
    current_user: dict[str, Any] = Depends(require_super_admin),
):
    del current_user
    service_state = get_service_state(include_operational_details=True)
    operational_ready = bool(service_state.get("operational_ready"))
    response.status_code = (
        status.HTTP_200_OK
        if operational_ready
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return {
        "status": "ok" if operational_ready else "unavailable",
        "service": "Tomb of Light API",
        **service_state,
    }
