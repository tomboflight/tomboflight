from fastapi import APIRouter, Depends, Request

from app.dependencies.auth import get_current_user
from app.services.lineage_query_service import LineageQueryService


router = APIRouter(prefix="/lineage-query", tags=["Lineage Query"])


@router.get("/ancestors/{member_id}")
async def get_ancestors(
    member_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    db = request.app.state.db
    service = LineageQueryService(db)
    return service.get_ancestors(member_id)


@router.get("/descendants/{member_id}")
async def get_descendants(
    member_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    db = request.app.state.db
    service = LineageQueryService(db)
    return service.get_descendants(member_id)


@router.get("/tree/{member_id}")
async def get_tree(
    member_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    db = request.app.state.db
    service = LineageQueryService(db)
    return service.get_tree(member_id)


@router.get("/family-graph/{family_id}")
async def get_family_graph(
    family_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    db = request.app.state.db
    service = LineageQueryService(db)
    return service.get_family_graph(family_id)


@router.get("/neighbors/{member_id}")
async def get_neighbors(
    member_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    db = request.app.state.db
    service = LineageQueryService(db)
    return service.get_member_neighbors(member_id)