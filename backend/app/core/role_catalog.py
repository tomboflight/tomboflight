from __future__ import annotations

from typing import Any, Iterable

ROLE_CODE_ALIASES: dict[str, str] = {
    "admin": "admin",
    "super_admin": "super_admin",
    "root_admin": "root_admin",
    "platform_admin": "platform_admin",
    "operations_admin": "operations_admin",
    "finance_admin": "finance_admin",
    "marketing_admin": "marketing_admin",
    "executive_technology": "executive_technology",
    "operations": "operations",
    "finance": "finance",
    "marketing": "marketing",
    "user": "user",
}

INTERNAL_ADMIN_ROLE_CODES: frozenset[str] = frozenset(
    {
        "admin",
        "super_admin",
        "root_admin",
        "platform_admin",
        "operations_admin",
        "finance_admin",
        "marketing_admin",
        "executive_technology",
        "operations",
        "finance",
        "marketing",
    }
)

PROJECT_MEMBER_ROLE_ALIASES: dict[str, str] = {
    "owner": "owner",
    "administrator": "manager",
    "admin": "manager",
    "manager": "manager",
    "editor": "editor",
    "contributor": "editor",
    "viewer": "viewer",
    "reader": "viewer",
}

PROJECT_MEMBER_ROLE_CODES: frozenset[str] = frozenset(
    {"owner", "manager", "editor", "viewer"}
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
