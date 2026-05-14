"""
Continuity Kernel shared isolated taxonomy module.

This module is isolated taxonomy only.
This module is non-operational.
This module does not execute repairs.
This module does not write to the database.
This module does not queue mint work.
This module does not mutate certificates.
This module does not alter customer records.
"""

from typing import Final


CANONICAL_OFFICER_ROLES: Final[tuple[str, ...]] = (
    "SUPERADMIN",
    "EXECUTIVE_TECH_ADMIN",
    "operations_admin",
    "finance_admin",
    "marketing_admin",
    "CMO",
)
CANONICAL_OFFICER_ROLE_SET: Final[frozenset[str]] = frozenset(CANONICAL_OFFICER_ROLES)

CANONICAL_REPAIR_CATEGORIES: Final[tuple[str, ...]] = (
    "missing_entitlement_repair",
    "package_lane_normalization",
    "workspace_membership_repair",
    "upload_readiness_repair",
    "viewer_readiness_repair",
    "certificate_issuance_consistency_repair",
    "mint_readiness_repair",
    "admin_repair_safety",
    "billing_order_payment_repair",
    "audit_record_correction_metadata",
)
CANONICAL_REPAIR_CATEGORY_SET: Final[frozenset[str]] = frozenset(CANONICAL_REPAIR_CATEGORIES)

TECHNICAL_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "missing_entitlement_repair",
        "package_lane_normalization",
        "certificate_issuance_consistency_repair",
        "mint_readiness_repair",
        "audit_record_correction_metadata",
    }
)
OPERATIONS_CATEGORIES: Final[frozenset[str]] = frozenset(
    {
        "workspace_membership_repair",
        "upload_readiness_repair",
        "viewer_readiness_repair",
    }
)
FINANCE_CATEGORIES: Final[frozenset[str]] = frozenset({"billing_order_payment_repair"})
MARKETING_CATEGORIES: Final[frozenset[str]] = frozenset()
SUPERADMIN_ONLY_CATEGORIES: Final[frozenset[str]] = frozenset({"admin_repair_safety"})
READ_ONLY_PREVIEW_CATEGORIES: Final[frozenset[str]] = frozenset(CANONICAL_REPAIR_CATEGORIES)

ROLE_TO_ALLOWED_CATEGORIES: Final[dict[str, frozenset[str]]] = {
    "SUPERADMIN": frozenset(CANONICAL_REPAIR_CATEGORIES),
    "EXECUTIVE_TECH_ADMIN": TECHNICAL_CATEGORIES,
    "operations_admin": OPERATIONS_CATEGORIES,
    "finance_admin": FINANCE_CATEGORIES,
    "marketing_admin": MARKETING_CATEGORIES,
    "CMO": MARKETING_CATEGORIES,
}

ROLE_TO_PREVIEW_CATEGORIES: Final[dict[str, frozenset[str]]] = {
    "SUPERADMIN": READ_ONLY_PREVIEW_CATEGORIES,
    "EXECUTIVE_TECH_ADMIN": TECHNICAL_CATEGORIES,
    "operations_admin": OPERATIONS_CATEGORIES,
    "finance_admin": FINANCE_CATEGORIES,
    "marketing_admin": MARKETING_CATEGORIES,
    "CMO": MARKETING_CATEGORIES,
}


def _normalize_text(value: str) -> str:
    return value.strip()


def is_canonical_role(role: str) -> bool:
    return _normalize_text(role) in CANONICAL_OFFICER_ROLE_SET


def is_canonical_repair_category(category: str) -> bool:
    return _normalize_text(category) in CANONICAL_REPAIR_CATEGORY_SET


def allowed_categories_for_role(role: str) -> frozenset[str]:
    return ROLE_TO_ALLOWED_CATEGORIES.get(_normalize_text(role), frozenset())


def preview_categories_for_role(role: str) -> frozenset[str]:
    return ROLE_TO_PREVIEW_CATEGORIES.get(_normalize_text(role), frozenset())


def is_marketing_role(role: str) -> bool:
    return _normalize_text(role) in {"marketing_admin", "CMO"}


def is_finance_category(category: str) -> bool:
    return _normalize_text(category) in FINANCE_CATEGORIES


def is_superadmin_only_category(category: str) -> bool:
    return _normalize_text(category) in SUPERADMIN_ONLY_CATEGORIES
