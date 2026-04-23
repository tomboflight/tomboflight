from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from bson import ObjectId
from pymongo.database import Database

from app.database import get_database
from app.services.audit_log_service import write_audit_log
from app.services.mint_policy_service import (
    READINESS_REASON_DETAILS,
    describe_project_mint_eligibility,
)

TERMINAL_STATUSES = {"paid", "waived", "included", "executed"}


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _now() -> datetime:
    return datetime.now(UTC)


def _db() -> Database:
    db = cast(Database | None, get_database())
    if db is None:
        raise RuntimeError("Database is not connected.")
    return db


def _project(project_id: str) -> dict[str, Any]:
    if not ObjectId.is_valid(project_id):
        raise ValueError("Project not found.")
    project = _db()["projects"].find_one({"_id": ObjectId(project_id)})
    if not isinstance(project, dict):
        raise ValueError("Project not found.")
    return project


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, float(value or default))
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value or default))
    except (TypeError, ValueError):
        return default


def _base_mint_fee_state(project: dict[str, Any]) -> dict[str, Any]:
    eligibility = describe_project_mint_eligibility(project)
    policy = dict(eligibility.get("mint_policy") or {})
    included_anchor_count = _as_int(policy.get("included_anchor_count"), 0)
    minting_included = bool(policy.get("minting_included", included_anchor_count > 0))
    mint_fee_model = _normalize(policy.get("mint_fee_model") or ("flat_included" if minting_included else "service_plus_network"))

    return {
        "project_id": _normalize(project.get("_id") or project.get("id")),
        "mint_fee_model": mint_fee_model,
        "minting_included": minting_included,
        "included_anchor_count": included_anchor_count,
        "mints_used_count": _as_int(project.get("mints_used_count"), 0),
        "minting_service_fee_usd": _as_float(policy.get("minting_service_fee_usd"), 0.0),
        "blockchain_network_fee_usd": _as_float(project.get("blockchain_network_fee_usd") or policy.get("network_fee_quote_usd"), 0.0),
        "additional_mint_service_fee_usd": _as_float(policy.get("additional_mint_service_fee_usd"), 0.0),
        "remint_service_fee_usd": _as_float(policy.get("remint_service_fee_usd"), 0.0),
        "network_fee_quote_usd": _as_float(project.get("network_fee_quote_usd") or policy.get("network_fee_quote_usd"), 0.0),
        "network_fee_quote_expires_at": project.get("network_fee_quote_expires_at"),
        "mint_fee_status": _normalize(project.get("mint_fee_status")) or "not_required",
        "mint_fee_paid_at": project.get("mint_fee_paid_at"),
        "network_fee_locked_at": project.get("network_fee_locked_at"),
        "mint_fee_notes": _normalize(project.get("mint_fee_notes")),
    }


def get_project_mint_fee(project_id: str) -> dict[str, Any]:
    project = _project(project_id)
    state = _base_mint_fee_state(project)

    if not bool(describe_project_mint_eligibility(project).get("mint_policy", {}).get("product_includes_onchain_anchor")):
        state["mint_fee_status"] = "not_required"

    return state


def _create_order_line_item(
    *,
    project_id: str,
    package_code: str,
    item_type: str,
    amount_usd: float,
    status: str,
    quote_expires_at: datetime | None,
    notes: str,
) -> None:
    _db()["order_line_items"].insert_one(
        {
            "project_id": project_id,
            "package_code": package_code,
            "item_type": item_type,
            "amount_usd": amount_usd,
            "status": status,
            "quote_expires_at": quote_expires_at,
            "mint_fee_notes": notes,
            "created_at": _now(),
            "updated_at": _now(),
        }
    )


def _write_fee_audit(action: str, project_id: str, actor: dict[str, Any], before: dict[str, Any], after: dict[str, Any]) -> None:
    write_audit_log(
        actor_user_id=_normalize(actor.get("id") or actor.get("_id") or actor.get("user_id")) or None,
        actor_email=_normalize(actor.get("email")).lower() or None,
        actor_name=_normalize(actor.get("name") or actor.get("full_name")) or None,
        action=action,
        target_type="project",
        target_id=project_id,
        before=before,
        after=after,
        details={"mint_fee_billing": True},
    )


def quote_mint_fee(project_id: str, actor: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    project = _project(project_id)
    before = _base_mint_fee_state(project)
    fee_notes = _normalize(payload.get("mint_fee_notes"))
    expires_at = _now() + timedelta(minutes=max(5, int(payload.get("quote_ttl_minutes") or 60)))

    update = {
        "minting_service_fee_usd": _as_float(payload.get("minting_service_fee_usd"), before["minting_service_fee_usd"]),
        "blockchain_network_fee_usd": _as_float(payload.get("blockchain_network_fee_usd"), before["blockchain_network_fee_usd"]),
        "network_fee_quote_usd": _as_float(payload.get("network_fee_quote_usd"), before["network_fee_quote_usd"]),
        "network_fee_quote_expires_at": expires_at,
        "mint_fee_status": "quoted",
        "mint_fee_notes": fee_notes,
        "updated_at": _now(),
    }
    _db()["projects"].update_one({"_id": project["_id"]}, {"$set": update})

    package_code = _normalize(project.get("package_code") or project.get("package_slug"))
    _create_order_line_item(
        project_id=project_id,
        package_code=package_code,
        item_type="minting_service_fee",
        amount_usd=update["minting_service_fee_usd"],
        status="quoted",
        quote_expires_at=expires_at,
        notes=fee_notes,
    )
    _create_order_line_item(
        project_id=project_id,
        package_code=package_code,
        item_type="blockchain_network_fee",
        amount_usd=update["blockchain_network_fee_usd"],
        status="quoted",
        quote_expires_at=expires_at,
        notes=fee_notes,
    )

    after = get_project_mint_fee(project_id)
    _write_fee_audit("project_mint_fee_quoted", project_id, actor, before, after)
    return after


def mark_mint_fee_paid(project_id: str, actor: dict[str, Any], notes: str = "") -> dict[str, Any]:
    project = _project(project_id)
    before = _base_mint_fee_state(project)
    now = _now()
    _db()["projects"].update_one(
        {"_id": project["_id"]},
        {
            "$set": {
                "mint_fee_status": "paid",
                "mint_fee_paid_at": now,
                "network_fee_locked_at": now,
                "mint_fee_notes": _normalize(notes) or before.get("mint_fee_notes") or "",
                "updated_at": now,
            }
        },
    )
    _db()["order_line_items"].update_many(
        {"project_id": project_id, "item_type": {"$in": ["minting_service_fee", "blockchain_network_fee", "remint_fee"]}},
        {"$set": {"status": "paid", "updated_at": now}},
    )
    after = get_project_mint_fee(project_id)
    _write_fee_audit("project_mint_fee_marked_paid", project_id, actor, before, after)
    return after


def waive_mint_fee(project_id: str, actor: dict[str, Any], notes: str = "") -> dict[str, Any]:
    project = _project(project_id)
    before = _base_mint_fee_state(project)
    now = _now()
    _db()["projects"].update_one(
        {"_id": project["_id"]},
        {
            "$set": {
                "mint_fee_status": "waived",
                "mint_fee_notes": _normalize(notes) or "Admin waived mint fee.",
                "updated_at": now,
            }
        },
    )
    _db()["order_line_items"].update_many(
        {"project_id": project_id, "item_type": {"$in": ["minting_service_fee", "blockchain_network_fee", "remint_fee"]}},
        {"$set": {"status": "waived", "updated_at": now}},
    )
    after = get_project_mint_fee(project_id)
    _write_fee_audit("project_mint_fee_waived", project_id, actor, before, after)
    return after


def refresh_network_quote(project_id: str, actor: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    project = _project(project_id)
    before = _base_mint_fee_state(project)
    expires_at = _now() + timedelta(minutes=max(5, int(payload.get("quote_ttl_minutes") or 60)))
    _db()["projects"].update_one(
        {"_id": project["_id"]},
        {
            "$set": {
                "network_fee_quote_usd": _as_float(payload.get("network_fee_quote_usd"), before["network_fee_quote_usd"]),
                "network_fee_quote_expires_at": expires_at,
                "mint_fee_status": "quoted",
                "mint_fee_notes": _normalize(payload.get("mint_fee_notes")) or before.get("mint_fee_notes") or "",
                "updated_at": _now(),
            }
        },
    )
    after = get_project_mint_fee(project_id)
    _write_fee_audit("project_mint_fee_network_quote_refreshed", project_id, actor, before, after)
    return after


def mint_fee_satisfied(project: dict[str, Any]) -> tuple[bool, str | None]:
    state = _base_mint_fee_state(project)
    status = _normalize(state.get("mint_fee_status")).lower()
    included = bool(state.get("minting_included")) and _as_int(state.get("mints_used_count"), 0) < _as_int(state.get("included_anchor_count"), 0)
    model = _normalize(state.get("mint_fee_model"))

    if model == "flat_included" and included:
        return True, None
    if status in TERMINAL_STATUSES:
        return True, None
    if included and model in {"flat_included", "flat_fee"}:
        return True, None
    return False, "mint_fee_unpaid_or_unwaived"


def get_project_mint_readiness(project_id: str) -> dict[str, Any]:
    project = _project(project_id)
    eligibility = describe_project_mint_eligibility(project)
    fee_ok, fee_reason = mint_fee_satisfied(project)
    reasons = list(eligibility.get("reasons") or [])
    blocking_details = list(eligibility.get("blocking_details") or [])
    if not fee_ok and fee_reason:
        reasons.append(fee_reason)
        blocking_details.append(
            {
                "code": fee_reason,
                "message": (READINESS_REASON_DETAILS.get(fee_reason) or {}).get("message")
                or fee_reason.replace("_", " "),
                "flag": (READINESS_REASON_DETAILS.get(fee_reason) or {}).get("flag"),
            }
        )
    return {
        "project_id": project_id,
        "mint_eligible": bool(eligibility.get("eligible")),
        "mint_policy": eligibility.get("mint_policy") or {},
        "mint_fee": _base_mint_fee_state(project),
        "ready_for_mint_preparation": bool(eligibility.get("eligible")),
        "ready_for_mint_execution": bool(eligibility.get("eligible")) and fee_ok,
        "blocking_reasons": reasons,
        "blocking_details": blocking_details,
        "missing_readiness_flags": [
            str(detail.get("flag")).strip()
            for detail in blocking_details
            if str(detail.get("flag") or "").strip()
        ],
    }
