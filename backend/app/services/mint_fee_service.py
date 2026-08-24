from __future__ import annotations

from typing import Any, cast

from bson import ObjectId
from pymongo.database import Database

from app.database import get_database
from app.services.mint_policy_service import (
    READINESS_REASON_DETAILS,
    describe_project_mint_eligibility,
)

def _normalize(value: Any) -> str:
    return str(value or "").strip()


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
    addon_status = dict(eligibility.get("nft_addon") or {})
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
        "mint_fee_status": (
            "paid_addon_claimed"
            if addon_status.get("active_mint_credit")
            else "paid_addon_available"
            if addon_status.get("mint_credit_satisfied")
            else "nft_addon_required"
        ),
        "required_nft_addon_code": addon_status.get("required_mint_addon_code"),
        "verified_paid_addon_credit": bool(addon_status.get("mint_credit_satisfied")),
        "checkout_never_triggers_mint": True,
        "mint_fee_paid_at": project.get("mint_fee_paid_at"),
        "network_fee_locked_at": project.get("network_fee_locked_at"),
        "mint_fee_notes": _normalize(project.get("mint_fee_notes")),
    }


def get_project_mint_fee(project_id: str) -> dict[str, Any]:
    project = _project(project_id)
    return _base_mint_fee_state(project)


def quote_mint_fee(project_id: str, actor: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    del project_id, actor, payload
    raise ValueError(
        "Separate mint-fee quotes are disabled. Use the exact verified NFT add-on price."
    )


def mark_mint_fee_paid(project_id: str, actor: dict[str, Any], notes: str = "") -> dict[str, Any]:
    del project_id, actor, notes
    raise ValueError(
        "Manual fee status cannot authorize minting. The customer must purchase the verified NFT add-on."
    )


def waive_mint_fee(project_id: str, actor: dict[str, Any], notes: str = "") -> dict[str, Any]:
    del project_id, actor, notes
    raise ValueError(
        "NFT add-on purchases cannot be waived into existence. A verified paid add-on is required."
    )


def refresh_network_quote(project_id: str, actor: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    del project_id, actor, payload
    raise ValueError(
        "Separate network-fee quotes are disabled. Network execution is fulfilled through the verified NFT add-on."
    )


def mint_fee_satisfied(project: dict[str, Any]) -> tuple[bool, str | None]:
    state = _base_mint_fee_state(project)
    if bool(state.get("verified_paid_addon_credit")):
        return True, None
    return False, "nft_addon_not_purchased"


def get_project_mint_readiness(project_id: str) -> dict[str, Any]:
    project = _project(project_id)
    eligibility = describe_project_mint_eligibility(project)
    fee_ok, fee_reason = mint_fee_satisfied(project)
    reasons = list(eligibility.get("reasons") or [])
    blocking_details = list(eligibility.get("blocking_details") or [])
    if not fee_ok and fee_reason and fee_reason not in reasons:
        reasons.append(fee_reason)
    if (
        not fee_ok
        and fee_reason
        and not any(detail.get("code") == fee_reason for detail in blocking_details)
    ):
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
        "ready_for_mint_preparation": bool(
            eligibility.get("ready_for_mint_preparation")
        ),
        "ready_for_mint_execution": bool(eligibility.get("eligible")) and fee_ok,
        "blocking_reasons": reasons,
        "blocking_details": blocking_details,
        "missing_readiness_flags": [
            str(detail.get("flag")).strip()
            for detail in blocking_details
            if str(detail.get("flag") or "").strip()
        ],
    }
