from __future__ import annotations

from typing import Any

RELATIONSHIP_TYPE_ALIASES: dict[str, str] = {
    "parent_child": "biological_parent",
    "parent-child": "biological_parent",
    "biological_parent": "biological_parent",
    "biological-parent": "biological_parent",
    "spouse": "spouse",
    "spousal": "spouse",
    "former_spouse": "former_spouse",
    "former-spouse": "former_spouse",
    "sibling": "sibling",
    "guardian": "guardian",
    "adoptive_parent_child": "adoptive_parent",
    "adoptive-parent-child": "adoptive_parent",
    "adoptive_parent": "adoptive_parent",
    "adoptive-parent": "adoptive_parent",
    "step_parent_child": "step_parent",
    "step-parent-child": "step_parent",
    "step_parent": "step_parent",
    "step-parent": "step_parent",
    "step parent": "step_parent",
    "stepparent": "step_parent",
    "household_member": "household_member",
    "household-member": "household_member",
}

ALLOWED_RELATIONSHIP_TYPES: tuple[str, ...] = (
    "biological_parent",
    "adoptive_parent",
    "step_parent",
    "guardian",
    "spouse",
    "former_spouse",
    "sibling",
    "household_member",
)

ALLOWED_RELATIONSHIP_TYPE_SET: frozenset[str] = frozenset(ALLOWED_RELATIONSHIP_TYPES)
SYMMETRIC_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {"spouse", "former_spouse", "sibling", "household_member"}
)
ANCESTRY_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {"biological_parent", "adoptive_parent", "step_parent", "guardian"}
)
BIOLOGICAL_PARENT_RELATIONSHIP_TYPE = "biological_parent"



def normalize_relationship_type(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return RELATIONSHIP_TYPE_ALIASES.get(normalized, normalized)



def is_allowed_relationship_type(value: Any) -> bool:
    return normalize_relationship_type(value) in ALLOWED_RELATIONSHIP_TYPE_SET
