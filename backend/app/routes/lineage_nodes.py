from fastapi import APIRouter

from app.schemas.lineage_node import (
    LineageNodeCreate,
    LineageNodeResponse,
    build_lineage_node_response,
)
from app.services.lineage_node_service import create_lineage_node, list_lineage_nodes

router = APIRouter(prefix="/lineage-nodes", tags=["Lineage Nodes"])


@router.get("/", response_model=list[LineageNodeResponse])
def get_lineage_nodes():
    nodes = list_lineage_nodes()
    return [build_lineage_node_response(node) for node in nodes]


@router.post("/", response_model=LineageNodeResponse)
def create_lineage_node_route(payload: LineageNodeCreate):
    node = create_lineage_node(payload)
    return build_lineage_node_response(node)
