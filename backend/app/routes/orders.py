from fastapi import APIRouter, Depends, Query, status

from app.dependencies.auth import get_current_user, require_admin
from app.schemas.order import OrderCreate, OrderResponse
from app.services.order_service import (
    create_order_for_user,
    ensure_order_indexes,
    get_orders_for_user,
    list_recent_orders,
)

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.on_event("startup")
def startup_indexes():
    ensure_order_indexes()


@router.post(
    "/record-checkout",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_checkout_order(
    payload: OrderCreate,
    current_user: dict = Depends(get_current_user),
):
    return create_order_for_user(current_user, payload)


@router.get("/my-orders", response_model=list[OrderResponse])
def my_orders(current_user: dict = Depends(get_current_user)):
    return get_orders_for_user(current_user)


@router.get("/admin/all")
def list_all_orders_admin(
    limit: int = Query(default=100, ge=1, le=500),
    status_filter: str = Query(default="", alias="status"),
    search: str = Query(default=""),
    current_user: dict = Depends(require_admin),
):
    del current_user
    return {
        "items": list_recent_orders(
            limit=limit,
            status=status_filter,
            search=search,
        )
    }


@router.get("/health")
def orders_health():
    return {"message": "Orders route is active."}
