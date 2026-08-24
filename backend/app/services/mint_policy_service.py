from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.config import settings
from app.core.package_catalog import (
    get_package_catalog,
    get_package_control_profile,
)
from app.core.package_mapping import resolve_package_identity
from app.database import get_database

COMPLETE_PROFILE_STATUSES = {"delivered", "archived"}
COMPLETE_PROFILE_PHASES = {"delivery_complete", "delivered", "archived"}

MINT_FEE_STATUS_READY = {"paid", "waived", "included", "executed"}

READINESS_REASON_DETAILS: dict[str, dict[str, str]] = {
    "nft_addon_not_purchased": {
        "message": "A verified paid NFT mint add-on is required.",
        "flag": "paid_nft_addon_credit",
    },
    "profile_not_complete": {
        "message": "The customer profile must be delivered before an NFT add-on can be purchased or prepared.",
        "flag": "profile_complete",
    },
    "mint_runtime_disabled": {
        "message": "Mint runtime flags are disabled for this token type.",
        "flag": "runtime_enabled",
    },
    "controlled_mint_worker_disabled": {
        "message": "The controlled mint worker is disabled.",
        "flag": "nft_mint_worker_enabled",
    },
    "public_safe_approval_incomplete": {
        "message": "Public-safe approval is incomplete.",
        "flag": "public_safe_approved",
    },
    "delivery_manifest_not_finalized": {
        "message": "Delivery/public manifest has not been finalized.",
        "flag": "delivery_manifest_finalized",
    },
    "collectible_not_preparing": {
        "message": "Collectible preparation has not started.",
        "flag": "mint_collectible_preparing",
    },
}

def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _get_project(project_id: str) -> dict[str, Any] | None:
    db = get_database()
    if db is None or not ObjectId.is_valid(project_id):
        return None
    return db["projects"].find_one({"_id": ObjectId(project_id)})


def _package_code_from_project(project: dict[str, Any]) -> str:
    identity = resolve_package_identity(
        _normalize(
            project.get("package_code")
            or project.get("package_slug")
            or project.get("package_type")
        )
    )
    return _normalize(identity.get("package_code")) or _normalize(
        project.get("package_code")
        or project.get("package_slug")
        or project.get("package_type")
    )


def _package_lane_from_project(project: dict[str, Any]) -> str:
    identity = resolve_package_identity(_package_code_from_project(project))
    return _normalize(identity.get("lane")) or _normalize(project.get("project_lane"))


def _runtime_enabled(token_type: str | None) -> bool:
    if not token_type:
        return False
    if token_type == "organization_anchor":
        return bool(settings.nft_mint_enabled and settings.nft_org_mint_enabled)
    return bool(settings.nft_mint_enabled)


def _project_has_build_state(project: dict[str, Any]) -> bool:
    status_value = _normalize(project.get("status")).lower()
    phase_value = _normalize(project.get("phase")).lower()
    return status_value in COMPLETE_PROFILE_STATUSES or phase_value in COMPLETE_PROFILE_PHASES




def _project_public_safe_approved(project: dict[str, Any]) -> bool:
    return bool(
        project.get("public_safe_approved")
        or project.get("public_safe_approval_complete")
        or project.get("delivery_safe_approved")
    )


def _delivery_manifest_finalized(project: dict[str, Any]) -> bool:
    return bool(project.get("delivery_manifest_finalized") or project.get("public_manifest_finalized"))

def get_package_mint_policy(package_code: str) -> dict[str, Any]:
    identity = resolve_package_identity(package_code)
    normalized_code = _normalize(identity.get("package_code")) or _normalize(package_code)
    package_name = _normalize(identity.get("display_name")) or normalized_code
    package_lane = _normalize(identity.get("lane"))
    control_profile = get_package_control_profile(normalized_code) or {}
    base_policy = dict(control_profile.get("mint_policy") or {})
    launch_policy = dict(control_profile.get("launch_policy") or {})

    token_type = base_policy.get("token_type")

    return {
        "package_code": normalized_code,
        "package_slug": normalized_code,
        "package_name": package_name,
        "package_lane": package_lane,
        "anchor_type": control_profile.get("anchor_type"),
        "launch_policy": {
            "allows_automatic_anchor": bool(launch_policy.get("allows_automatic_anchor")),
            "requires_runtime_flag_for_auto_mint": bool(
                launch_policy.get("requires_runtime_flag_for_auto_mint", True)
            ),
        },
        "maintenance_default": control_profile.get("maintenance_default") or "monthly",
        "token_type": token_type,
        "product_includes_onchain_anchor": bool(
            base_policy.get("product_includes_onchain_anchor")
        ),
        "onchain_anchor_available_as_addon": bool(
            base_policy.get("onchain_anchor_available_as_addon")
        ),
        "requires_paid_nft_addon": bool(base_policy.get("requires_paid_nft_addon")),
        "profile_completion_required_before_purchase": bool(
            base_policy.get("profile_completion_required_before_purchase")
        ),
        "checkout_never_triggers_mint": bool(
            base_policy.get("checkout_never_triggers_mint", True)
        ),
        "auto_mint_enabled": bool(base_policy.get("auto_mint_enabled")),
        "opt_in_only": bool(base_policy.get("opt_in_only")),
        "requires_customer_public_safe_approval": bool(
            base_policy.get("requires_customer_public_safe_approval")
        ),
        "requires_admin_final_approval": bool(
            base_policy.get("requires_admin_final_approval")
        ),
        "included_anchor_count": int(base_policy.get("included_anchor_count") or 0),
        "mint_fee_model": str(base_policy.get("mint_fee_model") or "service_plus_network"),
        "minting_included": bool(base_policy.get("minting_included", int(base_policy.get("included_anchor_count") or 0) > 0)),
        "minting_service_fee_usd": float(base_policy.get("minting_service_fee_usd") or 0),
        "additional_mint_service_fee_usd": float(base_policy.get("additional_mint_service_fee_usd") or 0),
        "remint_service_fee_usd": float(base_policy.get("remint_service_fee_usd") or 0),
        "network_fee_quote_usd": float(base_policy.get("network_fee_quote_usd") or 0),
        "default_network_fee_policy": str(base_policy.get("default_network_fee_policy") or "quoted_variable"),
        "initial_mint_addon_code": str(base_policy.get("initial_mint_addon_code") or ""),
        "additional_mint_addon_code": str(base_policy.get("additional_mint_addon_code") or ""),
        "metadata_revision_addon_code": str(base_policy.get("metadata_revision_addon_code") or ""),
        "runtime_enabled": _runtime_enabled(token_type),
    }


def list_package_mint_policies() -> list[dict[str, Any]]:
    policies: list[dict[str, Any]] = []
    for package_code in get_package_catalog():
        policies.append(get_package_mint_policy(package_code))
    return policies


def resolve_token_type(project: dict[str, Any]) -> str | None:
    policy = get_package_mint_policy(_package_code_from_project(project))
    return str(policy.get("token_type") or "").strip() or None


def describe_project_mint_eligibility(project: dict[str, Any]) -> dict[str, Any]:
    package_code = _package_code_from_project(project)
    package_lane = _package_lane_from_project(project)
    policy = get_package_mint_policy(package_code)
    reasons: list[str] = []

    profile_complete = _project_has_build_state(project)
    if not profile_complete:
        reasons.append("profile_not_complete")

    project_id = _normalize(project.get("_id") or project.get("id"))
    try:
        from app.services.nft_addon_service import get_nft_addon_status

        addon_status = get_nft_addon_status(project_id, project=project)
    except (RuntimeError, ValueError):
        addon_status = {
            "project_id": project_id,
            "profile_complete": profile_complete,
            "required_mint_addon_code": policy.get("initial_mint_addon_code"),
            "mint_credit_satisfied": False,
            "checkout_never_triggers_mint": True,
            "purchase_options": {},
        }

    if policy.get("requires_paid_nft_addon") and not addon_status.get("mint_credit_satisfied"):
        reasons.append("nft_addon_not_purchased")

    if not policy.get("runtime_enabled"):
        reasons.append("mint_runtime_disabled")
    elif not settings.nft_mint_worker_enabled:
        reasons.append("controlled_mint_worker_disabled")

    if not _project_public_safe_approved(project):
        reasons.append("public_safe_approval_incomplete")

    if not _delivery_manifest_finalized(project):
        reasons.append("delivery_manifest_not_finalized")

    if not bool(project.get("mint_collectible_preparing") or project.get("mint_preparation_started")):
        reasons.append("collectible_not_preparing")

    blocking_details = [
        {
            "code": reason,
            "message": (READINESS_REASON_DETAILS.get(reason) or {}).get("message")
            or reason.replace("_", " "),
            "flag": (READINESS_REASON_DETAILS.get(reason) or {}).get("flag"),
        }
        for reason in reasons
    ]
    return {
        "project_id": project_id,
        "package_code": package_code,
        "package_lane": package_lane,
        "mint_policy": policy,
        "nft_addon": addon_status,
        "profile_complete": profile_complete,
        "purchase_eligible": bool(
            profile_complete
            and addon_status.get("purchase_runtime_ready")
            and any(
                bool((option or {}).get("eligible"))
                for option in (addon_status.get("purchase_options") or {}).values()
            )
        ),
        "ready_for_mint_preparation": bool(
            profile_complete and addon_status.get("mint_credit_satisfied")
        ),
        "eligible": len(reasons) == 0,
        "reasons": reasons,
        "blocking_details": blocking_details,
        "missing_readiness_flags": [
            detail["flag"] for detail in blocking_details if _normalize(detail.get("flag"))
        ],
    }


def project_is_mint_eligible(project_id: str) -> dict[str, Any]:
    project = _get_project(project_id)
    if project is None:
        raise ValueError("Project not found.")
    return describe_project_mint_eligibility(project)
