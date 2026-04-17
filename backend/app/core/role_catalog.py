from __future__ import annotations

INTERNAL_ADMIN_KEYS = {
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

DEFAULT_USER_PERMISSIONS = {
    "projects.read",
    "uploads.read",
    "uploads.write",
}

LEGACY_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        "admin.access",
        "projects.create",
        "verification.review",
        "uploads.admin.review",
        "project.workflow.transition",
    },
    "super_admin": {"*"},
    "root_admin": {"*"},
    "platform_admin": {"*"},
    "operations_admin": {
        "admin.access",
        "verification.review",
        "uploads.admin.review",
        "project.workflow.transition",
    },
    "finance_admin": {"admin.access"},
    "marketing_admin": {"admin.access"},
    "executive_technology": {"*"},
    "operations": {"admin.access", "verification.review", "uploads.admin.review"},
    "finance": {"admin.access"},
    "marketing": {"admin.access"},
    "user": set(DEFAULT_USER_PERMISSIONS),
}

ALL_ROLE_CODES = frozenset(LEGACY_ROLE_PERMISSIONS.keys())


def is_admin_role(role_code: str) -> bool:
    return str(role_code or "").strip().lower() in INTERNAL_ADMIN_KEYS
