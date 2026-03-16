from fastapi import APIRouter, HTTPException

from app.schemas.db_bootstrap import BootstrapResponse
from app.services.db_bootstrap_service import bootstrap_core_collections

router = APIRouter(
    prefix="/db-bootstrap",
    tags=["Database Bootstrap"],
)


@router.post("/", response_model=BootstrapResponse)
def run_db_bootstrap():
    try:
        return bootstrap_core_collections()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Bootstrap failed: {exc}",
        ) from exc