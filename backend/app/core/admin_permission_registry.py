from __future__ import annotations

from typing import Any

from app.core.role_catalog import normalize_role_code

PERMISSION_REGISTRY: dict[str, dict[str, str]] = {
    "admin.access": {"name": "Admin Workspace Access", "description": "Access shared admin workspace data."},
    "admin.control.view": {"name": "Admin Control View", "description": "View admin control center case data."},
    "admin.control.write": {"name": "Admin Control Write", "description": "Run non-billing admin repair actions."},
    "admin.control.billing": {"name": "Admin Billing Controls", "description": "Run billing and order repair actions."},
    "admin.control.mint": {"name": "Admin Mint Controls", "description": "Run mint readiness and mint repair actions."},
    "admin.audit.read": {"name": "Audit Read", "description": "Read operational audit logs."},
    "admin.entitlements.read": {"name": "Entitlements Read", "description": "Read project entitlement state."},
    "admin.entitlements.write": {"name": "Entitlements Write", "description": "Repair and write entitlement state."},
    "admin.orders.read": {"name": "Orders Read", "description": "Read orders and payment status."},
    "admin.orders.repair": {"name": "Orders Repair", "description": "Repair order linkage and status records."},
    "admin.intake.review": {"name": "Intake Review", "description": "Review intake submissions and queue state."},
    "admin.intake.write": {"name": "Intake Write", "description": "Approve/reject/provision intake submissions."},
    "admin.users.read": {"name": "Users Read", "description": "Read customer and admin user accounts."},
    "admin.users.write": {"name": "Users Write", "description": "Update user accounts and role assignments."},
    "admin.marketing.content.read": {"name": "Marketing Content Read", "description": "Read marketing content controls."},
    "admin.marketing.content.write": {"name": "Marketing Content Write", "description": "Manage marketing content controls."},
    "admin.analytics.read": {"name": "Analytics Read", "description": "Read dashboard analytics and reporting data."},
    "projects.create": {"name": "Projects Create", "description": "Create new project records."},
    "project.workflow.transition": {"name": "Project Workflow Transition", "description": "Transition project workflow states."},
    "uploads.admin.review": {"name": "Upload Review", "description": "Review upload and verification artifacts."},
    "verification.review": {"name": "Verification Review", "description": "Review identity verification records."},
}

CAPABILITY_PERMISSIONS: dict[str, set[str]] = {
    "manage_roles": {"admin.users.write"},
    "manage_users_full": {"admin.users.read", "admin.users.write"},
    "manage_user_contact": {"admin.users.read", "admin.control.view", "admin.control.write"},
    "manage_orders": {"admin.orders.read", "admin.orders.repair", "admin.control.billing"},
    "manage_entitlements": {"admin.entitlements.read", "admin.entitlements.write"},
    "manage_packages": {"admin.control.write"},
    "manage_projects": {"admin.control.view", "project.workflow.transition"},
    "manage_families": {"admin.access", "admin.intake.review", "admin.intake.write"},
    "manage_billing": {"admin.control.billing"},
    "manage_marketing_content": {"admin.marketing.content.read", "admin.marketing.content.write"},
    "view_audit_all": {"admin.audit.read"},
    "run_admin_repairs": {"admin.control.write", "admin.control.mint"},
    "read_finance_scope": {"admin.entitlements.read", "admin.control.view"},
    "read_analytics": {"admin.analytics.read"},
    "read_operations_scope": {"admin.access", "admin.control.view", "admin.intake.review"},
}

ROLE_CAPABILITIES: dict[str, set[str]] = {
    # Deprecated generic admin role: no implicit capability grants.
    "admin": set(),
    "super_admin": {"*"},
    "executive_tech_admin": {
        "manage_roles",
        "manage_users_full",
        "manage_user_contact",
        "manage_orders",
        "manage_entitlements",
        "manage_packages",
        "manage_projects",
        "manage_families",
        "run_admin_repairs",
        "view_audit_all",
        "read_finance_scope",
        "read_analytics",
    },
    "operations_admin": {
        "manage_user_contact",
        "manage_projects",
        "manage_families",
        "run_admin_repairs",
        "view_audit_all",
        "read_operations_scope",
    },
    "finance_admin": {
        "manage_billing",
        "manage_orders",
        "view_audit_all",
        "read_finance_scope",
    },
    "marketing_admin": {
        "manage_marketing_content",
        "read_analytics",
    },
    "user": set(),
}

ROLE_PERMISSION_MAP: dict[str, set[str]] = {
    # Deprecated generic admin role: no implicit permission grants.
    "admin": set(),
    "super_admin": {"*"},
    "executive_tech_admin": {
        "admin.access",
        "admin.audit.read",
        "admin.control.view",
        "admin.control.write",
        "admin.control.billing",
        "admin.control.mint",
        "admin.entitlements.read",
        "admin.entitlements.write",
        "admin.intake.review",
        "admin.intake.write",
        "admin.orders.read",
        "admin.orders.repair",
        "admin.users.read",
        "admin.users.write",
        "project.workflow.transition",
        "uploads.admin.review",
        "verification.review",
    },
    "operations_admin": {
        "admin.access",
        "admin.audit.read",
        "admin.control.view",
        "admin.control.write",
        "admin.control.mint",
        "admin.entitlements.read",
        "admin.intake.review",
        "admin.intake.write",
        "admin.orders.read",
        "project.workflow.transition",
        "uploads.admin.review",
        "verification.review",
    },
    "finance_admin": {
        "admin.audit.read",
        "admin.control.view",
        "admin.control.billing",
        "admin.entitlements.read",
        "admin.orders.read",
        "admin.orders.repair",
    },
    "marketing_admin": {
        "admin.marketing.content.read",
        "admin.marketing.content.write",
        "admin.analytics.read",
    },
    "user": {"projects.read", "uploads.read", "uploads.write"},
}

ROLE_METADATA: dict[str, dict[str, str]] = {
    "super_admin": {
        "name": "Super Admin",
        "description": "Break-glass emergency full override controls.",
    },
    "executive_tech_admin": {
        "name": "Executive Technical Admin",
        "description": "Executive technical operations and admin control center access.",
    },
    "operations_admin": {
        "name": "Chief Operating Officer",
        "description": "Operational intake, fulfillment, and support controls.",
    },
    "finance_admin": {
        "name": "Chief Financial Officer",
        "description": "Finance dashboards, billing, and reconciliation controls.",
    },
    "marketing_admin": {
        "name": "Chief Marketing Officer",
        "description": "Marketing dashboards, analytics, and content controls.",
    },
}

OFFICER_ROLE_MAPPING: dict[str, list[str]] = {
    "l.robinson@tomboflight.com": ["SUPERADMIN", "EXECUTIVE_TECH_ADMIN"],
    "marquis.l.floyd@tomboflight.com": ["CMO_ADMIN"],
    "jenn.wood@tomboflight.com": ["CFO_ADMIN"],
    "k.goffigan@tomboflight.com": ["COO_ADMIN"],
}

OFFICER_PROFILE_FIELDS: dict[str, dict[str, str]] = {
    "l.robinson@tomboflight.com": {
        "full_name": "Larry Robinson",
        "business_title": "CEO",
        "access_tier": "super_admin",
        "department_role": "executive_tech_admin",
    },
    "marquis.l.floyd@tomboflight.com": {
        "full_name": "Marquis Floyd",
        "business_title": "CMO",
        "access_tier": "marketing_admin",
        "department_role": "marketing_admin",
    },
    "jenn.wood@tomboflight.com": {
        "full_name": "Jennifer Wood",
        "business_title": "CFO",
        "access_tier": "finance_admin",
        "department_role": "finance_admin",
    },
    "k.goffigan@tomboflight.com": {
        "full_name": "Keith Goffigan",
        "business_title": "COO",
        "access_tier": "operations_admin",
        "department_role": "operations_admin",
    },
}


def normalize_officer_role(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "superadmin":
        normalized = "super_admin"
    return normalize_role_code(normalized)


def normalized_officer_role_mapping() -> dict[str, list[str]]:
    normalized_mapping: dict[str, list[str]] = {}
    for email, role_codes in OFFICER_ROLE_MAPPING.items():
        normalized_email = str(email or "").strip().lower()
        if not normalized_email:
            continue
        roles = [
            role_code
            for role_code in (normalize_officer_role(value) for value in role_codes)
            if role_code
        ]
        if roles:
            normalized_mapping[normalized_email] = sorted(set(roles))
    return normalized_mapping

