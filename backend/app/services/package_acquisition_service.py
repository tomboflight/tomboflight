from __future__ import annotations

import logging
from typing import Any

from bson import ObjectId

from app.core.package_mapping import resolve_package_identity
from app.core.package_type_catalog import normalize_package_type
from app.database import get_database
from app.services.audit_log_service import create_audit_log
from app.services.entitlement_service import resolve_project_entitlements

PAID_PACKAGE_STATUSES = frozenset({"paid", "complete", "completed", "succeeded"})
GOVERNED_PACKAGE_GRANT_TYPES = frozenset(
    {"complimentary_package", "promotional_package", "internal_validation_account"}
)
GOVERNED_PACKAGE_GRANT_SOURCE = "ceo_admin_assignment"
GOVERNED_PACKAGE_GRANT_AUTHORITY = "ceo_master_admin"

_logger = logging.getLogger(__name__)


class ProjectAcquisitionError(PermissionError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = str(reason or "").strip()


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _to_object_id(value: Any) -> ObjectId | None:
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _project_id_candidates(project_id: str) -> list[Any]:
    normalized = _normalize(project_id)
    if not normalized:
        return []
    candidates: list[Any] = [normalized]
    oid = _to_object_id(normalized)
    if oid is not None:
        candidates.append(oid)
    return candidates


def _db():
    db = get_database()
    if db is None:
        raise ProjectAcquisitionError("database_unavailable", "Database is not connected.")
    return db


def _get_active_entitlement(project_id: str) -> dict[str, Any] | None:
    return _db()["project_entitlements"].find_one(
        {"project_id": {"$in": _project_id_candidates(project_id)}, "status": "active"}
    )


def _is_paid_package_order(order: dict[str, Any] | None) -> bool:
    if not isinstance(order, dict):
        return False
    item_type = _normalize(order.get("item_type") or "package").lower()
    status = _normalize(order.get("status")).lower()
    return item_type == "package" and status in PAID_PACKAGE_STATUSES


def _get_paid_package_order(project_id: str) -> dict[str, Any] | None:
    cursor = _db()["orders"].find(
        {"project_id": {"$in": _project_id_candidates(project_id)}}
    ).sort("created_at", -1)
    for order in cursor:
        if _is_paid_package_order(order):
            return order
    return None


def _is_governed_package_assignment(assignment: dict[str, Any] | None) -> bool:
    if not isinstance(assignment, dict):
        return False
    return bool(
        _normalize(assignment.get("status")).lower() == "active"
        and assignment.get("payment_required") is False
        and _normalize(assignment.get("source")).lower() == GOVERNED_PACKAGE_GRANT_SOURCE
        and _normalize(assignment.get("authorization_source")).lower()
        == GOVERNED_PACKAGE_GRANT_AUTHORITY
        and _normalize(assignment.get("billing_classification")).lower()
        in GOVERNED_PACKAGE_GRANT_TYPES
        and _normalize(assignment.get("new_package"))
    )


def _get_active_governed_package_assignment(project_id: str) -> dict[str, Any] | None:
    cursor = _db()["admin_package_assignments"].find(
        {"project_id": {"$in": _project_id_candidates(project_id)}, "status": "active"}
    ).sort("assigned_at", -1)
    for assignment in cursor:
        if _is_governed_package_assignment(assignment):
            return assignment
    return None


def _package_code_from_identity(value: Any) -> str:
    identity = resolve_package_identity(value)
    return _normalize(identity.get("package_code") or value)


def _package_lane_from_identity(value: Any, fallback: Any = "") -> str:
    identity = resolve_package_identity(value)
    return normalize_package_type(
        _normalize(identity.get("package_lane") or identity.get("lane") or fallback),
        default="",
    )


def _audit_drift(
    project_id: str,
    reason: str,
    *,
    entitlement: dict[str, Any] | None = None,
    paid_order: dict[str, Any] | None = None,
    governed_assignment: dict[str, Any] | None = None,
) -> None:
    try:
        create_audit_log(
            "verified_package_acquisition_drift",
            None,
            "project",
            _normalize(project_id),
            {
                "reason": _normalize(reason),
                "entitlement_package_code": _normalize((entitlement or {}).get("package_code")),
                "entitlement_package_lane": _normalize((entitlement or {}).get("package_lane")),
                "paid_order_id": _normalize((paid_order or {}).get("_id")) or None,
                "paid_order_package_code": _normalize(
                    (paid_order or {}).get("package_code") or (paid_order or {}).get("package_slug")
                )
                or None,
                "governed_assignment_id": _normalize((governed_assignment or {}).get("_id")) or None,
                "governed_assignment_package_code": _normalize(
                    (governed_assignment or {}).get("new_package")
                )
                or None,
                "governed_assignment_authority": _normalize(
                    (governed_assignment or {}).get("authorization_source")
                )
                or None,
            },
        )
    except Exception as exc:
        _logger.warning(
            "verified_package_acquisition_audit_failed",
            extra={"project_id": _normalize(project_id), "reason": _normalize(reason)},
            exc_info=exc,
        )


def resolve_verified_project_acquisition(project_id: str) -> dict[str, Any]:
    """Verify the package authority behind a protected customer workspace.

    A workspace is valid only when it has an active entitlement plus one of
    the two supported acquisition authorities:

    1. an authoritative paid package order, or
    2. an active CEO-governed complimentary/promotional/internal-validation
       assignment that explicitly records payment_required=False.

    Raw package fields stored on a project document are never an acquisition
    authority and cannot unlock protected capabilities.
    """

    normalized_project_id = _normalize(project_id)
    if not normalized_project_id:
        raise ProjectAcquisitionError("no_active_project", "Workspace project id is required.")

    entitlement = _get_active_entitlement(normalized_project_id)
    if entitlement is None:
        _audit_drift(normalized_project_id, "missing_active_entitlement")
        raise ProjectAcquisitionError(
            "missing_active_entitlement",
            "Active workspace entitlement is required.",
        )

    entitlement_package_code = _package_code_from_identity(entitlement.get("package_code"))
    entitlement_lane = _package_lane_from_identity(
        entitlement.get("package_code"),
        entitlement.get("package_lane"),
    )
    if not entitlement_package_code:
        _audit_drift(
            normalized_project_id,
            "unresolved_package_identity",
            entitlement=entitlement,
        )
        raise ProjectAcquisitionError(
            "entitlement_package_mismatch",
            "Workspace entitlement package identity could not be verified.",
        )

    paid_order = _get_paid_package_order(normalized_project_id)
    governed_assignment = _get_active_governed_package_assignment(normalized_project_id)

    sources: list[dict[str, Any]] = []
    if paid_order is not None:
        paid_code_raw = paid_order.get("package_code") or paid_order.get("package_slug")
        sources.append(
            {
                "source": "paid_order",
                "record": paid_order,
                "package_code": _package_code_from_identity(paid_code_raw),
                "package_lane": _package_lane_from_identity(
                    paid_code_raw,
                    paid_order.get("package_lane") or paid_order.get("project_lane"),
                ),
                "payment_required": True,
            }
        )
    if governed_assignment is not None:
        grant_code_raw = governed_assignment.get("new_package")
        sources.append(
            {
                "source": "governed_grant",
                "record": governed_assignment,
                "package_code": _package_code_from_identity(grant_code_raw),
                "package_lane": _package_lane_from_identity(grant_code_raw),
                "payment_required": False,
            }
        )

    if not sources:
        _audit_drift(
            normalized_project_id,
            "missing_acquisition_source",
            entitlement=entitlement,
        )
        raise ProjectAcquisitionError(
            "missing_acquisition_source",
            "A verified paid package order or CEO-governed package grant is required.",
        )

    matching_sources = [
        source for source in sources if source.get("package_code") == entitlement_package_code
    ]
    if not matching_sources:
        _audit_drift(
            normalized_project_id,
            "package_code_mismatch",
            entitlement=entitlement,
            paid_order=paid_order,
            governed_assignment=governed_assignment,
        )
        raise ProjectAcquisitionError(
            "package_code_mismatch",
            "Workspace entitlement does not match its verified package acquisition authority.",
        )

    # Prefer a paid acquisition when both authorities happen to describe the
    # same current package; otherwise the matching governed grant is valid.
    selected = next(
        (source for source in matching_sources if source.get("source") == "paid_order"),
        matching_sources[0],
    )
    source_lane = _normalize(selected.get("package_lane"))
    if not entitlement_lane or not source_lane:
        _audit_drift(
            normalized_project_id,
            "missing_package_lane",
            entitlement=entitlement,
            paid_order=paid_order,
            governed_assignment=governed_assignment,
        )
        raise ProjectAcquisitionError(
            "entitlement_lane_mismatch",
            "Workspace package lane could not be verified.",
        )
    if entitlement_lane != source_lane:
        _audit_drift(
            normalized_project_id,
            "package_lane_mismatch",
            entitlement=entitlement,
            paid_order=paid_order,
            governed_assignment=governed_assignment,
        )
        raise ProjectAcquisitionError(
            "package_lane_mismatch",
            "Workspace entitlement lane does not match its package acquisition authority.",
        )

    active_addons = list(entitlement.get("active_addons") or [])
    try:
        resolved_entitlements = resolve_project_entitlements(
            entitlement_package_code,
            active_addons,
        )
    except Exception as exc:
        _audit_drift(
            normalized_project_id,
            "entitlement_resolution_failed",
            entitlement=entitlement,
            paid_order=paid_order,
            governed_assignment=governed_assignment,
        )
        raise ProjectAcquisitionError(
            "missing_active_entitlement",
            "Workspace entitlement could not be resolved.",
        ) from exc

    acquisition_source = _normalize(selected.get("source"))
    acquisition_record = selected.get("record") or {}
    return {
        "project_id": normalized_project_id,
        "package_code": entitlement_package_code,
        "package_lane": entitlement_lane,
        "active_addons": active_addons,
        "resolved_entitlements": resolved_entitlements,
        "entitlement": entitlement,
        "paid_order": paid_order if acquisition_source == "paid_order" else None,
        "governed_assignment": (
            governed_assignment if acquisition_source == "governed_grant" else None
        ),
        "acquisition_source": acquisition_source,
        "acquisition_record": acquisition_record,
        "payment_required": bool(selected.get("payment_required")),
    }
