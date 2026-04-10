from __future__ import annotations

from typing import Any

VISIBILITY_STATE_ALIASES: dict[str, str] = {
    "private": "private",
    "family": "family_only",
    "family_only": "family_only",
    "family-only": "family_only",
    "public": "certificate_only",
    "certificate_only": "certificate_only",
    "certificate-only": "certificate_only",
}

APPROVAL_STATE_ALIASES: dict[str, str] = {
    "pending": "pending",
    "pending_review": "pending",
    "awaiting_review": "pending",
    "approved": "approved",
    "rejected": "rejected",
}

RELATIONSHIP_LINK_STATE_ALIASES: dict[str, str] = {
    "active": "active",
    "linked": "active",
    "pending": "pending",
    "pending_review": "pending",
    "inactive": "inactive",
    "archived": "archived",
}

TRUST_STATE_ALIASES: dict[str, str] = {
    "pending": "pending",
    "unverified": "pending",
    "verified": "verified",
    "flagged": "flagged",
}

NARRATIVE_STATE_ALIASES: dict[str, str] = {
    "draft": "draft",
    "private": "private",
    "family_only": "family_only",
    "family-only": "family_only",
    "certificate_only": "certificate_only",
    "certificate-only": "certificate_only",
    "published": "published",
}

ACTIVE_RECORD_STATES: frozenset[str] = frozenset({"active", "enabled"})



def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()



def normalize_visibility_state(value: Any, *, default: str = "private") -> str:
    normalized = _normalize(value)
    if not normalized:
        return default
    return VISIBILITY_STATE_ALIASES.get(normalized, default)



def normalize_approval_state(value: Any, *, default: str = "pending") -> str:
    normalized = _normalize(value)
    if not normalized:
        return default
    return APPROVAL_STATE_ALIASES.get(normalized, default)



def normalize_relationship_link_state(value: Any, *, default: str = "active") -> str:
    normalized = _normalize(value)
    if not normalized:
        return default
    return RELATIONSHIP_LINK_STATE_ALIASES.get(normalized, default)



def is_active_record_state(value: Any) -> bool:
    return _normalize(value) in ACTIVE_RECORD_STATES
