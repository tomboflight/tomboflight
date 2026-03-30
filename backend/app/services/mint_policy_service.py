from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.config import settings
from app.core.package_catalog import get_package, get_package_catalog
from app.database import get_database

BUILD_READY_STATUSES = {
    "build_ready",
    "in_production",
    "qa_review",
    "client_review",
    "delivered",
    "archived",
}
BUILD_READY_PHASES = {
    "intake_approved",
    "in_production",
    "qa_review",
    "client_review",
    "delivered",
    "archived",
}

PACKAGE_MINT_POLICIES: dict[str, dict[str, Any]] = {
    "legacy_snapshot": {
        "product_includes_onchain_anchor": False,
        "auto_mint_enabled": False,
        "opt_in_only": False,
        "token_type": None,
        "included_anchor_count": 0,
        "requires_customer_public_safe_approval": False,
    },
    "legacy_portrait_intro": {
        "product_includes_onchain_anchor": False,
        "auto_mint_enabled": False,
        "opt_in_only": False,
        "token_type": None,
        "included_anchor_count": 0,
        "requires_customer_public_safe_approval": False,
    },
    "digital_legacy_portrait": {
        "product_includes_onchain_anchor": True,
        "auto_mint_enabled": True,
        "opt_in_only": False,
        "token_type": "portrait_anchor",
        "included_anchor_count": 1,
        "requires_customer_public_safe_approval": True,
    },
    "household_foundation": {
        "product_includes_onchain_anchor": True,
        "auto_mint_enabled": True,
        "opt_in_only": False,
        "token_type": "household_anchor",
        "included_anchor_count": 1,
        "requires_customer_public_safe_approval": True,
    },
    "heirloom_legacy_tree": {
        "product_includes_onchain_anchor": True,
        "auto_mint_enabled": True,
        "opt_in_only": False,
        "token_type": "household_anchor",
        "included_anchor_count": 1,
        "requires_customer_public_safe_approval": True,
    },
    "legacy_plus": {
        "product_includes_onchain_anchor": True,
        "auto_mint_enabled": True,
        "opt_in_only": False,
        "token_type": "household_anchor",
        "included_anchor_count": 1,
        "requires_customer_public_safe_approval": True,
    },
    "family_estate_concierge": {
        "product_includes_onchain_anchor": True,
        "auto_mint_enabled": True,
        "opt_in_only": False,
        "token_type": "branch_anchor",
        "included_anchor_count": 3,
        "requires_customer_public_safe_approval": True,
    },
    "command_structure_network": {
        "product_includes_onchain_anchor": True,
        "auto_mint_enabled": False,
        "opt_in_only": True,
        "token_type": "organization_anchor",
        "included_anchor_count": 1,
        "requires_customer_public_safe_approval": True,
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
    package = get_package(
        _normalize(
            project.get("package_code")
            or project.get("package_slug")
            or project.get("package_type")
        )
    )
    return _normalize((package or {}).get("package_code")) or _normalize(
        project.get("package_code")
        or project.get("package_slug")
        or project.get("package_type")
    )


def _package_lane_from_project(project: dict[str, Any]) -> str:
    package = get_package(_package_code_from_project(project))
    return _normalize((package or {}).get("package_lane")) or _normalize(
        project.get("project_lane")
    )


def _runtime_enabled(token_type: str | None) -> bool:
    if not token_type:
        return False
    if token_type == "organization_anchor":
        return bool(settings.nft_mint_enabled and settings.nft_org_mint_enabled)
    return bool(settings.nft_mint_enabled)


def _project_has_build_state(project: dict[str, Any]) -> bool:
    status_value = _normalize(project.get("status")).lower()
    phase_value = _normalize(project.get("phase")).lower()
    return (
        status_value in BUILD_READY_STATUSES or phase_value in BUILD_READY_PHASES
    )


def get_package_mint_policy(package_code: str) -> dict[str, Any]:
    package = get_package(package_code)
    normalized_code = _normalize((package or {}).get("package_code")) or _normalize(
        package_code
    )
    package_name = _normalize((package or {}).get("display_name")) or normalized_code
    package_lane = _normalize((package or {}).get("package_lane"))

    base_policy = PACKAGE_MINT_POLICIES.get(
        normalized_code,
        {
            "product_includes_onchain_anchor": False,
            "auto_mint_enabled": False,
            "opt_in_only": False,
            "token_type": None,
            "included_anchor_count": 0,
            "requires_customer_public_safe_approval": False,
        },
    )

    token_type = base_policy.get("token_type")

    return {
        "package_code": normalized_code,
        "package_name": package_name,
        "package_lane": package_lane,
        "token_type": token_type,
        "product_includes_onchain_anchor": bool(
            base_policy.get("product_includes_onchain_anchor")
        ),
        "auto_mint_enabled": bool(base_policy.get("auto_mint_enabled")),
        "opt_in_only": bool(base_policy.get("opt_in_only")),
        "requires_customer_public_safe_approval": bool(
            base_policy.get("requires_customer_public_safe_approval")
        ),
        "included_anchor_count": int(base_policy.get("included_anchor_count") or 0),
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

    if not policy.get("product_includes_onchain_anchor"):
        reasons.append("package_not_included")

    if not _project_has_build_state(project):
        reasons.append("build_not_ready")

    if (
        policy.get("product_includes_onchain_anchor")
        and not policy.get("runtime_enabled")
    ):
        reasons.append("mint_runtime_disabled")

    return {
        "project_id": _normalize(project.get("_id") or project.get("id")),
        "package_code": package_code,
        "package_lane": package_lane,
        "mint_policy": policy,
        "eligible": len(reasons) == 0,
        "reasons": reasons,
    }


def project_is_mint_eligible(project_id: str) -> dict[str, Any]:
    project = _get_project(project_id)
    if project is None:
        raise ValueError("Project not found.")
    return describe_project_mint_eligibility(project)
