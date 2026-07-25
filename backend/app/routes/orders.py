from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user, require_any_permission, require_permission
from app.schemas.order import AdminManualOrderCreate, OrderResponse, PublicCheckoutOrderCreate
from app.services.order_service import (
    create_manual_order_for_admin,
    create_order_for_user,
    ensure_order_indexes,
    get_orders_for_user,
    list_recent_orders,
    repair_paid_package_order_access,
)

router = APIRouter(prefix="/orders", tags=["Orders"])


def initialize_order_indexes() -> None:
    ensure_order_indexes()


@router.post(
    "/record-checkout",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_checkout_order(
    payload: PublicCheckoutOrderCreate,
    current_user: dict = Depends(get_current_user),
):
    try:
        return create_order_for_user(current_user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/admin/manual-order",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_order_admin(
    payload: AdminManualOrderCreate,
    current_user: dict = Depends(
        require_any_permission(["admin.control.billing", "admin.orders.repair"])
    ),
):
    try:
        return create_manual_order_for_admin(current_user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/my-orders", response_model=list[OrderResponse])
def my_orders(current_user: dict = Depends(get_current_user)):
    return get_orders_for_user(current_user)


@router.get("/admin/all")
def list_all_orders_admin(
    limit: int = Query(default=100, ge=1, le=500),
    status_filter: str = Query(default="", alias="status"),
    search: str = Query(default=""),
    current_user: dict = Depends(require_permission("admin.orders.read")),
):
    del current_user
    return {
        "items": list_recent_orders(
            limit=limit,
            status=status_filter,
            search=search,
        )
    }


@router.post("/admin/repair-paid-package-access")
def repair_paid_package_access_admin(
    limit: int = Query(default=500, ge=1, le=1000),
    current_user: dict = Depends(require_permission("admin.orders.repair")),
):
    del current_user
    return repair_paid_package_order_access(limit=limit)


@router.get("/health")
def orders_health():
    return {"message": "Orders route is active."}
