from fastapi import APIRouter

from app.schemas.family_network import (
    FamilyNetworkCreate,
    FamilyNetworkResponse,
    build_family_network_response,
)
from app.services.family_network_service import (
    create_family_network,
    list_family_networks,
)

router = APIRouter(prefix="/family-networks", tags=["Family Networks"])


@router.get("/", response_model=list[FamilyNetworkResponse])
def get_family_networks():
    networks = list_family_networks()
    return [build_family_network_response(network) for network in networks]


@router.post("/", response_model=FamilyNetworkResponse)
def create_family_network_route(payload: FamilyNetworkCreate):
    network = create_family_network(payload)
    return build_family_network_response(network)
