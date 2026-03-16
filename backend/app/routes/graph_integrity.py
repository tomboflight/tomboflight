from fastapi import APIRouter, HTTPException

from app.schemas.graph_integrity import GraphIntegrityResponse
from app.services.graph_integrity_service import analyze_family_graph_integrity

router = APIRouter(
    prefix="/graph-integrity",
    tags=["Graph Integrity"],
)


@router.get("/{family_id}", response_model=GraphIntegrityResponse)
def get_graph_integrity_report(family_id: str):
    try:
        return analyze_family_graph_integrity(family_id)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if "Family not found" in message else 500
        raise HTTPException(status_code=status_code, detail=message) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Graph integrity analysis failed: {exc}",
        ) from exc