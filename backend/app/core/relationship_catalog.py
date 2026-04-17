from __future__ import annotations

ALLOWED_RELATIONSHIP_TYPES = frozenset(
    {
        "parent_child",
        "spouse",
        "sibling",
        "guardian",
        "adoptive_parent_child",
        "step_parent_child",
    }
)

ANCESTRY_RELATIONSHIP_TYPES = frozenset(
    {
        "parent_child",
        "adoptive_parent_child",
        "step_parent_child",
    }
)

SYMMETRIC_RELATIONSHIP_TYPES = frozenset({"spouse", "sibling"})

# Stored in relationships for backward compatibility, but explicitly excluded from lineage ancestry traversal.
HOUSEHOLD_LINK_TYPES = frozenset({"linked_household"})
LINKED_HOUSEHOLD_RELATIONSHIP_TYPE = "linked_household"

ALL_RELATIONSHIP_TYPES = frozenset(ALLOWED_RELATIONSHIP_TYPES | HOUSEHOLD_LINK_TYPES)

BIOLOGICAL_PARENT_RELATIONSHIP_TYPE = "parent_child"
MIN_PARENT_CHILD_AGE_GAP = 12

RELATIONSHIP_TYPE_LITERAL_VALUES = tuple(sorted(ALLOWED_RELATIONSHIP_TYPES))


def is_ancestry_type(relationship_type: str) -> bool:
    return str(relationship_type or "").strip().lower() in ANCESTRY_RELATIONSHIP_TYPES


def is_symmetric_type(relationship_type: str) -> bool:
    return str(relationship_type or "").strip().lower() in SYMMETRIC_RELATIONSHIP_TYPES
