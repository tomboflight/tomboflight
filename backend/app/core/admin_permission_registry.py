from __future__ import annotations

import json
import re
from typing import Any

from app.config import DEPLOYED_ENVIRONMENTS, settings
from app.core.role_catalog import normalize_role_code


_IDENTITY_EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)


def _normalize_identity_email(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized or not _IDENTITY_EMAIL_PATTERN.fullmatch(normalized):
        return ""
    return normalized


def is_canonical_ceo_email(value: Any) -> bool:
    """Return True only for the immutable CEO Master Administrator mailbox."""
    normalized = _normalize_identity_email(value)
    return bool(CEO_MASTER_ADMIN_EMAIL) and normalized == CEO_MASTER_ADMIN_EMAIL

# Job-scoped roles that the canonical CEO may assign to an active officer.
# The CEO singleton is intentionally excluded from this collection.
ASSIGNABLE_OFFICER_ROLE_CODES: tuple[str, ...] = (
    "executive_tech_admin",
    "operations_admin",
    "finance_admin",
    "marketing_admin",
)


def has_canonical_internal_admin_authority(user: dict[str, Any] | None) -> bool:
    """Return whether an identity has live internal administrator authority.

    Deprecated generic admin/super-admin labels intentionally do not qualify;
    they receive no authority elsewhere in the canonical permission policy.
    """
    if not user:
        return False
    if is_canonical_ceo_email(user.get("email")):
        return True
    role_values: list[Any] = [
        user.get("role"),
        user.get("access_tier"),
        user.get("department_role"),
    ]
    for key in ("role_codes", "admin_roles", "officer_roles"):
        values = user.get(key)
        if isinstance(values, (list, tuple, set, frozenset)):
            role_values.extend(values)
    role_codes = {
        normalize_role_code(value)
        for value in role_values
        if str(value or "").strip()
    }
    return bool(role_codes.intersection(ASSIGNABLE_OFFICER_ROLE_CODES))


def requires_privileged_mfa(user: dict[str, Any] | None) -> bool:
    """Return whether an identity's live authority must be MFA-bound."""
    return has_canonical_internal_admin_authority(user)

PERMISSION_REGISTRY: dict[str, dict[str, str]] = {
    "admin.access": {"name": "Admin Workspace Access", "description": "Access shared admin workspace data."},
    "admin.control.view": {"name": "Admin Control View", "description": "View admin control center case data."},
    "admin.control.write": {"name": "Admin Control Write", "description": "Run non-billing admin repair actions."},
    "admin.control.billing": {"name": "Admin Billing Controls", "description": "Run billing and order repair actions."},
    "admin.control.mint.readiness": {
        "name": "Admin Mint Readiness Controls",
        "description": "View mint readiness and queue projects for mint review handoff.",
    },
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
    "run_operations_progression": {"admin.control.write", "admin.control.mint.readiness"},
    "read_finance_scope": {"admin.entitlements.read", "admin.control.view"},
    "read_analytics": {"admin.analytics.read"},
    "read_operations_scope": {"admin.access", "admin.control.view", "admin.intake.review"},
}

ROLE_CAPABILITIES: dict[str, set[str]] = {
    # Deprecated generic admin role: no implicit capability grants.
    "admin": set(),
    # Generic super_admin is retained only as a legacy data label. Wildcard
    # authority belongs exclusively to the canonical CEO identity and is
    # granted through ceo_master_admin after the identity invariant is checked.
    "super_admin": set(),
    "ceo_master_admin": {"*"},
    "ceo_super_admin": {"*"},
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
        "run_operations_progression",
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
    "super_admin": set(),
    "ceo_master_admin": {"*"},
    "ceo_super_admin": {"*"},
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
        "admin.control.mint.readiness",
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
        "name": "Legacy Super Admin Label",
        "description": "Deprecated data label with no standalone authority.",
    },
    "ceo_super_admin": {
        "name": "CEO Super Admin",
        "description": "CEO-level full platform controls with required audit logging.",
    },
    "ceo_master_admin": {
        "name": "CEO Master Administrator",
        "description": "Canonical CEO-level master administrator role with full platform controls and audit logging.",
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

_ACTIVE_PROFILE_KEYS = frozenset(
    {"full_name", "business_title", "access_tier", "department_role"}
)
_RETIRED_PROFILE_KEYS = frozenset(
    {"full_name", "former_business_title", "retirement_reason"}
)


def _clean_profile(
    value: Any,
    *,
    allowed_keys: frozenset[str],
    item_label: str,
    errors: list[str],
) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        errors.append(f"{item_label}.profile must be an object.")
        return {}
    unknown_keys = sorted(set(value) - set(allowed_keys))
    if unknown_keys:
        errors.append(f"{item_label}.profile contains unsupported fields.")
    return {
        key: str(value.get(key) or "").strip()
        for key in allowed_keys
        if str(value.get(key) or "").strip()
    }


def _load_admin_identity_registry(raw_registry: str | None = None) -> tuple[
    str,
    dict[str, list[str]],
    dict[str, dict[str, str]],
    dict[str, dict[str, str]],
    tuple[str, ...],
    bool,
]:
    raw = (
        settings.admin_identity_registry_json_value
        if raw_registry is None
        else str(raw_registry or "").strip()
    )
    if not raw:
        return "", {}, {}, {}, (), False

    errors: list[str] = []
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return "", {}, {}, {}, ("ADMIN_IDENTITY_REGISTRY_JSON is not valid JSON.",), True

    if not isinstance(payload, dict):
        return "", {}, {}, {}, ("ADMIN_IDENTITY_REGISTRY_JSON must be a JSON object.",), True

    if set(payload) - {"active_officers", "retired_officers"}:
        errors.append("ADMIN_IDENTITY_REGISTRY_JSON contains unsupported top-level fields.")

    active_items = payload.get("active_officers", [])
    retired_items = payload.get("retired_officers", [])
    if not isinstance(active_items, list):
        errors.append("active_officers must be a list.")
        active_items = []
    if not isinstance(retired_items, list):
        errors.append("retired_officers must be a list.")
        retired_items = []

    role_mapping: dict[str, list[str]] = {}
    active_profiles: dict[str, dict[str, str]] = {}
    retired_profiles: dict[str, dict[str, str]] = {}
    ceo_emails: list[str] = []
    allowed_active_roles = set(ASSIGNABLE_OFFICER_ROLE_CODES) | {"ceo_master_admin"}

    for index, item in enumerate(active_items):
        item_label = f"active_officers[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{item_label} must be an object.")
            continue
        if set(item) - {"email", "role_codes", "profile"}:
            errors.append(f"{item_label} contains unsupported fields.")
        email = _normalize_identity_email(item.get("email"))
        if not email:
            errors.append(f"{item_label}.email must be a valid email address.")
            continue
        if email in role_mapping:
            errors.append(f"{item_label}.email duplicates another active identity.")
            continue

        raw_roles = item.get("role_codes")
        if not isinstance(raw_roles, list) or not raw_roles:
            errors.append(f"{item_label}.role_codes must be a non-empty list.")
            continue
        roles = sorted(
            {
                normalized
                for normalized in (normalize_role_code(value) for value in raw_roles)
                if normalized
            }
        )
        if not roles or any(role not in allowed_active_roles for role in roles):
            errors.append(f"{item_label}.role_codes contains an unsupported role.")
            continue
        if "ceo_master_admin" in roles:
            ceo_emails.append(email)

        profile = _clean_profile(
            item.get("profile"),
            allowed_keys=_ACTIVE_PROFILE_KEYS,
            item_label=item_label,
            errors=errors,
        )
        for field_name in ("access_tier", "department_role"):
            if profile.get(field_name):
                profile[field_name] = normalize_role_code(profile[field_name])
                if profile[field_name] not in allowed_active_roles:
                    errors.append(
                        f"{item_label}.profile.{field_name} contains an unsupported role."
                    )
                elif profile[field_name] not in roles:
                    errors.append(
                        f"{item_label}.profile.{field_name} must match an assigned role."
                    )
        role_mapping[email] = roles
        active_profiles[email] = profile

    for index, item in enumerate(retired_items):
        item_label = f"retired_officers[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{item_label} must be an object.")
            continue
        if set(item) - {"email", "profile"}:
            errors.append(f"{item_label} contains unsupported fields.")
        email = _normalize_identity_email(item.get("email"))
        if not email:
            errors.append(f"{item_label}.email must be a valid email address.")
            continue
        if email in role_mapping or email in retired_profiles:
            errors.append(f"{item_label}.email duplicates another configured identity.")
            continue
        retired_profiles[email] = _clean_profile(
            item.get("profile"),
            allowed_keys=_RETIRED_PROFILE_KEYS,
            item_label=item_label,
            errors=errors,
        )

    if len(ceo_emails) != 1:
        errors.append("Exactly one active identity must have ceo_master_admin authority.")

    ceo_email = ceo_emails[0] if len(ceo_emails) == 1 else ""
    return (
        ceo_email,
        role_mapping,
        active_profiles,
        retired_profiles,
        tuple(errors),
        True,
    )


(
    CEO_MASTER_ADMIN_EMAIL,
    OFFICER_ROLE_MAPPING,
    OFFICER_PROFILE_FIELDS,
    RETIRED_OFFICER_PROFILE_FIELDS,
    ADMIN_IDENTITY_REGISTRY_ERRORS,
    ADMIN_IDENTITY_REGISTRY_CONFIGURED,
) = _load_admin_identity_registry()


def validate_admin_identity_registry_configuration(*, require_config: bool | None = None) -> None:
    """Fail closed when the private officer identity registry is absent or invalid."""
    required = (
        str(settings.environment or "").strip().lower() in DEPLOYED_ENVIRONMENTS
        if require_config is None
        else bool(require_config)
    )
    if required and not ADMIN_IDENTITY_REGISTRY_CONFIGURED:
        raise RuntimeError(
            "ADMIN_IDENTITY_REGISTRY_JSON must be configured outside source control."
        )
    if ADMIN_IDENTITY_REGISTRY_ERRORS:
        raise RuntimeError(
            "ADMIN_IDENTITY_REGISTRY_JSON is invalid: "
            + " ".join(ADMIN_IDENTITY_REGISTRY_ERRORS)
        )


def normalize_officer_role(value: Any) -> str:
    normalized = str(value or "").strip().lower()
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
