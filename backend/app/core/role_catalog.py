from __future__ import annotations

from typing import Any, Iterable

ROLE_CODE_ALIASES: dict[str, str] = {
    "admin": "admin",
    "super_admin": "super_admin",
    "superadmin": "super_admin",
    "root_admin": "super_admin",
    "platform_admin": "super_admin",
    "ceo_master_admin": "ceo_master_admin",
    "ceo-master-admin": "ceo_master_admin",
    "ceo_super_admin": "ceo_master_admin",
    "ceo-super-admin": "ceo_master_admin",
    "ceo_admin": "ceo_master_admin",
    "ceo": "ceo_master_admin",
    "executive_tech_admin": "executive_tech_admin",
    "executive-tech-admin": "executive_tech_admin",
    "executive_technology": "executive_tech_admin",
    "cto_admin": "executive_tech_admin",
    "operations_admin": "operations_admin",
    "coo_admin": "operations_admin",
    "coo": "operations_admin",
    "finance_admin": "finance_admin",
    "cfo_admin": "finance_admin",
    "cfo": "finance_admin",
    "marketing_admin": "marketing_admin",
    "cmo_admin": "marketing_admin",
    "cmo": "marketing_admin",
    "operations": "operations_admin",
    "finance": "finance_admin",
    "marketing": "marketing_admin",
    "user": "user",
}

OFFICER_ROLE_CODES: tuple[str, ...] = (
    "super_admin",
    "ceo_master_admin",
    "executive_tech_admin",
    "operations_admin",
    "finance_admin",
    "marketing_admin",
)

INTERNAL_ADMIN_ROLE_CODES: frozenset[str] = frozenset(OFFICER_ROLE_CODES)

SUPER_ADMIN_ROLE_CODES: frozenset[str] = frozenset(
    {
        "super_admin",
        "ceo_master_admin",
    }
)

PROJECT_MEMBER_ROLE_ALIASES: dict[str, str] = {
    "billing_owner": "billing_owner",
    "owner": "billing_owner",
    "buyer": "billing_owner",
    "co_owner": "co_owner",
    "spouse": "co_owner",
    "partner": "co_owner",
    "family_manager": "family_manager",
    "manager": "family_manager",
    "administrator": "family_manager",
    "admin": "family_manager",
    "contributor": "contributor",
    "editor": "contributor",
    "viewer": "viewer",
    "reader": "viewer",
    "minor_viewer": "minor_viewer",
    "linked_relative": "linked_relative",
    "legacy_executor": "legacy_executor",
}

PROJECT_MEMBER_ROLE_CODES: frozenset[str] = frozenset(
    {
        "billing_owner",
        "co_owner",
        "family_manager",
        "contributor",
        "viewer",
        "minor_viewer",
        "linked_relative",
        "legacy_executor",
    }
)


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()



def normalize_role_code(value: Any) -> str:
    normalized = _normalize(value)
    return ROLE_CODE_ALIASES.get(normalized, normalized)



def normalize_project_member_role(value: Any, *, default: str = "viewer") -> str:
    normalized = _normalize(value)
    if not normalized:
        return default
    return PROJECT_MEMBER_ROLE_ALIASES.get(normalized, default)



def collect_role_codes(values: Iterable[Any]) -> set[str]:
    return {
        normalized
        for normalized in (normalize_role_code(value) for value in values)
        if normalized
    }



def has_internal_admin_role(values: Iterable[Any]) -> bool:
    return any(role_code in INTERNAL_ADMIN_ROLE_CODES for role_code in collect_role_codes(values))


def has_super_admin_role(values: Iterable[Any]) -> bool:
    return any(role_code in SUPER_ADMIN_ROLE_CODES for role_code in collect_role_codes(values))


def resolve_primary_role_code(values: Iterable[Any], *, default: str = "user") -> str:
    role_codes = collect_role_codes(values)
    for role_code in OFFICER_ROLE_CODES:
        if role_code in role_codes:
            return role_code
    if "admin" in role_codes:
        return "admin"
    return default
