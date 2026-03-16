from fastapi import APIRouter
from app.services.lineage_graph_service import build_lineage_graph

router = APIRouter(
    prefix="/lineage",
    tags=["lineage"]
)


@router.get("/{family_id}")
def get_lineage_graph(family_id: str):
    return build_lineage_graph(family_id)