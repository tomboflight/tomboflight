from __future__ import annotations

from typing import Any

from app.services.admin_control_service import (
    assign_missing_lanes,
    link_unlinked_paid_orders,
    normalize_broken_package_records,
    repair_missing_entitlements,
)


def normalize_paid_package_orders(*, limit: int = 500) -> dict[str, Any]:
    return normalize_broken_package_records(limit=limit)


def link_unlinked_paid_package_orders(*, limit: int = 500) -> dict[str, Any]:
    return link_unlinked_paid_orders(limit=limit)


def repair_missing_project_lanes(*, limit: int = 500) -> dict[str, Any]:
    return assign_missing_lanes(limit=limit)


def repair_missing_project_entitlements(*, limit: int = 500) -> dict[str, Any]:
    return repair_missing_entitlements(limit=limit)


def reconcile_paid_orders_and_projects(*, limit: int = 500) -> dict[str, Any]:
    normalized = normalize_paid_package_orders(limit=limit)
    linked = link_unlinked_paid_package_orders(limit=limit)
    lanes = repair_missing_project_lanes(limit=limit)
    entitlements = repair_missing_project_entitlements(limit=limit)
    return {
        "normalized_orders": normalized,
        "linked_paid_orders": linked,
        "repaired_lanes": lanes,
        "repaired_entitlements": entitlements,
    }


def provision_after_order_change(*, limit: int = 200) -> dict[str, Any]:
    return reconcile_paid_orders_and_projects(limit=limit)


def provision_after_project_change(*, limit: int = 200) -> dict[str, Any]:
    return reconcile_paid_orders_and_projects(limit=limit)
