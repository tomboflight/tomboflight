from __future__ import annotations

from typing import Any

# Relationship records always read source -> target. Parent-style labels therefore
# mean "source is this kind of parent/elder of target". Keeping direction explicit
# prevents a child/parent selection from silently landing in the wrong generation.
RELATIONSHIP_TYPE_ALIASES: dict[str, str] = {
    "parent_child": "biological_parent",
    "parent-child": "biological_parent",
    "parent": "biological_parent",
    "father": "biological_parent",
    "mother": "biological_parent",
    "biological-parent": "biological_parent",
    "gestational-parent": "gestational_parent",
    "donor-parent": "donor_parent",
    "intended-parent": "intended_parent",
    "adoptive_parent_child": "adoptive_parent",
    "adoptive-parent-child": "adoptive_parent",
    "adoptive-parent": "adoptive_parent",
    "foster-parent": "foster_parent",
    "step_parent_child": "step_parent",
    "step-parent-child": "step_parent",
    "step-parent": "step_parent",
    "step parent": "step_parent",
    "stepparent": "step_parent",
    "legal-guardian": "guardian",
    "chosen-parent": "chosen_parent",
    "community-parent": "community_parent",
    "spiritual-parent": "spiritual_parent",
    "spousal": "spouse",
    "former-spouse": "former_spouse",
    "domestic-partner": "domestic_partner",
    "former-partner": "former_partner",
    "co-parent": "co_parent",
    "half-sibling": "half_sibling",
    "stepsibling": "step_sibling",
    "step-sibling": "step_sibling",
    "adoptive-sibling": "adoptive_sibling",
    "chosen-sibling": "chosen_sibling",
    "grand-parent": "grandparent",
    "grand_parent": "grandparent",
    "aunt": "aunt_uncle",
    "uncle": "aunt_uncle",
    "aunt-uncle": "aunt_uncle",
    "god-parent": "godparent",
    "god_parent": "godparent",
    "clan-elder": "clan_elder",
    "spiritual-elder": "spiritual_elder",
    "in-law": "in_law",
    "family-friend": "family_friend",
    "household-member": "household_member",
    "linked-household": "linked_household",
    "same_person": "identity_bridge",
    "same-person": "identity_bridge",
}

ALLOWED_RELATIONSHIP_TYPES: tuple[str, ...] = (
    "parent_unspecified",
    "biological_parent",
    "gestational_parent",
    "donor_parent",
    "intended_parent",
    "adoptive_parent",
    "foster_parent",
    "step_parent",
    "guardian",
    "chosen_parent",
    "community_parent",
    "spiritual_parent",
    "spouse",
    "former_spouse",
    "domestic_partner",
    "former_partner",
    "co_parent",
    "sibling",
    "half_sibling",
    "step_sibling",
    "adoptive_sibling",
    "chosen_sibling",
    "cousin",
    "grandparent",
    "aunt_uncle",
    "godparent",
    "mentor",
    "clan_elder",
    "spiritual_elder",
    "in_law",
    "other_relative",
    "family_friend",
    "household_member",
    "identity_bridge",
    "linked_household",
)

ALLOWED_RELATIONSHIP_TYPE_SET: frozenset[str] = frozenset(ALLOWED_RELATIONSHIP_TYPES)

PARENT_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {
        "parent_unspecified",
        "biological_parent",
        "gestational_parent",
        "donor_parent",
        "intended_parent",
        "adoptive_parent",
        "foster_parent",
        "step_parent",
        "guardian",
        "chosen_parent",
        "community_parent",
        "spiritual_parent",
    }
)
ANCESTRY_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {*PARENT_RELATIONSHIP_TYPES, "grandparent", "aunt_uncle"}
)
PARTNER_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {"spouse", "former_spouse", "domestic_partner", "former_partner", "co_parent"}
)
SIBLING_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {"sibling", "half_sibling", "step_sibling", "adoptive_sibling", "chosen_sibling"}
)
SYMMETRIC_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {
        *PARTNER_RELATIONSHIP_TYPES,
        *SIBLING_RELATIONSHIP_TYPES,
        "cousin",
        "in_law",
        "family_friend",
        "household_member",
        "identity_bridge",
    }
)
PEER_PLACEMENT_RELATIONSHIP_TYPES: frozenset[str] = frozenset(
    {
        *PARTNER_RELATIONSHIP_TYPES,
        *SIBLING_RELATIONSHIP_TYPES,
        "cousin",
        "identity_bridge",
    }
)

BIOLOGICAL_PARENT_RELATIONSHIP_TYPE = "biological_parent"
LINKED_HOUSEHOLD_RELATIONSHIP_TYPE = "linked_household"

# Cross-household handshakes also need the inverse point of view. Internal
# family relationships remain canonical parent -> child records, while these
# bridge-only labels let a requester accurately say "my member is the child of
# their member" without swapping households or guessing at generation math.
LINK_BRIDGE_INVERSE_GENERATION_DELTAS: dict[str, int] = {
    "child": -1,
    "biological_child": -1,
    "gestational_child": -1,
    "donor_conceived_child": -1,
    "intended_child": -1,
    "adopted_child": -1,
    "foster_child": -1,
    "step_child": -1,
    "ward": -1,
    "chosen_child": -1,
    "community_child": -1,
    "spiritual_child": -1,
    "grandchild": -2,
    "niece_nephew": -1,
}
LINK_BRIDGE_INVERSE_CANONICAL_TYPES: dict[str, str] = {
    "child": "parent_unspecified",
    "biological_child": "biological_parent",
    "gestational_child": "gestational_parent",
    "donor_conceived_child": "donor_parent",
    "intended_child": "intended_parent",
    "adopted_child": "adoptive_parent",
    "foster_child": "foster_parent",
    "step_child": "step_parent",
    "ward": "guardian",
    "chosen_child": "chosen_parent",
    "community_child": "community_parent",
    "spiritual_child": "spiritual_parent",
    "grandchild": "grandparent",
    "niece_nephew": "aunt_uncle",
}

ALLOWED_RELATIONSHIP_MODES: frozenset[str] = frozenset({"verified", "narrative"})
ALLOWED_RELATIONSHIP_STATUS_MARKERS: frozenset[str] = frozenset(
    {"verified", "narrative", "pending", "disputed", "unknown"}
)
ALLOWED_RELATIONSHIP_PRIVACY_SCOPES: frozenset[str] = frozenset(
    {
        "private_to_owner",
        "private_to_owner_and_co_owner",
        "household_private",
        "branch_shared",
        "linked_family_shared",
        "public_memorial",
        "minor_protected",
    }
)


def normalize_relationship_type(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return RELATIONSHIP_TYPE_ALIASES.get(normalized, normalized)


def is_allowed_relationship_type(value: Any) -> bool:
    return normalize_relationship_type(value) in ALLOWED_RELATIONSHIP_TYPE_SET


def relationship_generation_delta(value: Any) -> int | None:
    """Return target generation minus source generation for a directed edge."""
    normalized = normalize_relationship_type(value)
    if normalized in PARENT_RELATIONSHIP_TYPES:
        return 1
    if normalized == "grandparent":
        return 2
    if normalized == "aunt_uncle":
        return 1
    if normalized in PEER_PLACEMENT_RELATIONSHIP_TYPES:
        return 0
    if normalized in LINK_BRIDGE_INVERSE_GENERATION_DELTAS:
        return LINK_BRIDGE_INVERSE_GENERATION_DELTAS[normalized]
    return None


def relationship_supports_tree_placement(value: Any) -> bool:
    return relationship_generation_delta(value) is not None
