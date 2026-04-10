from __future__ import annotations

from typing import Any

RELATIONSHIP_TYPE_ALIASES: dict[str, str] = {
    "parent_child": "parent_child",
    "parent-child": "parent_child",
    "spouse": "spouse",
    "spousal": "spouse",
    "sibling": "sibling",
    "guardian": "guardian",
    "adoptive_parent_child": "adoptive_parent_child",
    "adoptive-parent-child": "adoptive_parent_child",
    "step_parent_child": "step_parent_child",
    "step-parent-child": "step_parent_child",
}

ALLOWED_RELATIONSHIP_TYPES: tuple[str, ...] = (
    "parent_child",
    "spouse",
    "sibling",
    "guardian",
    "adoptive_parent_child",
    "step_parent_child",
)

ALLOWED_RELATIONSHIP_TYPE_SET: frozenset[str] = frozenset(ALLOWED_RELATIONSHIP_TYPES)
SYMMETRIC_RELATIONSHIP_TYPES: frozenset[str] = frozenset({"spouse", "sibling"})
ANCESTRY_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {"parent_child", "adoptive_parent_child", "step_parent_child"}
)
BIOLOGICAL_PARENT_RELATIONSHIP_TYPE = "parent_child"



def normalize_relationship_type(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return RELATIONSHIP_TYPE_ALIASES.get(normalized, normalized)



def is_allowed_relationship_type(value: Any) -> bool:
    return normalize_relationship_type(value) in ALLOWED_RELATIONSHIP_TYPE_SET
