from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from app.core.relationship_catalog import (
    PARENT_RELATIONSHIP_TYPES,
    PARTNER_RELATIONSHIP_TYPES,
    SIBLING_RELATIONSHIP_TYPES,
    normalize_relationship_type,
)


LINEAGE_CINEMA_COMPILER_VERSION = "tol-lineage-cinema-1.0"

_BLOCKED_RELATIONSHIP_MARKERS = {
    "pending",
    "disputed",
    "rejected",
    "revoked",
    "deleted",
}
_DIRECT_ANCESTRY_TYPES = {*PARENT_RELATIONSHIP_TYPES, "grandparent"}
_SIBLING_DERIVATION_PARENT_TYPES = {
    "parent_unspecified",
    "biological_parent",
    "gestational_parent",
    "donor_parent",
    "intended_parent",
    "adoptive_parent",
    "foster_parent",
    "step_parent",
}


def _value(value: Any) -> str:
    return str(value or "").strip()


def _coerce_generation(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _state_sort_key(state: dict[str, Any]) -> tuple[int, str, str]:
    generation = _coerce_generation(state.get("generation"))
    return (
        generation if generation is not None else 999_999,
        _value(state.get("title") or state.get("node")).lower(),
        _value(state.get("id")),
    )


def _relationship_is_active(relationship: dict[str, Any]) -> bool:
    marker = _value(relationship.get("status_marker")).lower()
    status = _value(relationship.get("status")).lower()
    return (
        marker not in _BLOCKED_RELATIONSHIP_MARKERS
        and status not in _BLOCKED_RELATIONSHIP_MARKERS
    )


def _visual_style(relationship_type: str, relationship: dict[str, Any]) -> str:
    marker = _value(relationship.get("status_marker")).lower()
    mode = _value(relationship.get("relationship_mode")).lower()
    if marker == "unknown":
        return "unknown"
    if relationship_type in {
        "step_parent",
        "foster_parent",
        "guardian",
        "chosen_parent",
        "community_parent",
        "spiritual_parent",
        "step_sibling",
        "chosen_sibling",
    }:
        return "dashed"
    if relationship_type in {"adoptive_parent", "adoptive_sibling"}:
        return "double"
    if relationship_type in {"former_spouse", "former_partner"}:
        return "historical"
    if relationship_type in PARTNER_RELATIONSHIP_TYPES:
        return "partner"
    if relationship_type in SIBLING_RELATIONSHIP_TYPES or relationship_type == "cousin":
        return "branch"
    if mode == "narrative":
        return "dotted"
    return "solid"


def _relationship_label(relationship_type: str, relationship: dict[str, Any]) -> str:
    return (
        _value(relationship.get("relationship_label"))
        or relationship_type.replace("_", " ").title()
    )


def compile_lineage_cinema(
    *,
    states: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    anchor_state_id: str = "",
) -> dict[str, Any]:
    """Compile approved member states into one deterministic cinematic tour.

    A member state represents content; a tour step represents one visit to that
    content. Tour steps may therefore revisit an ancestor or anchor without
    duplicating the underlying person. This distinction prevents repeated graph
    states from trapping autoplay at their first sequence occurrence.
    """

    state_by_id = {
        _value(state.get("id")): dict(state)
        for state in states
        if _value(state.get("id"))
    }
    sorted_states = sorted(state_by_id.values(), key=_state_sort_key)
    state_ids = [_value(state.get("id")) for state in sorted_states]
    if not state_ids:
        return {
            "compiler_version": LINEAGE_CINEMA_COMPILER_VERSION,
            "ordered_state_ids": [],
            "tour_steps": [],
            "auto_advance_state_ids": [],
            "path_items": [],
            "branch_options_by_state": {},
            "navigation_by_state": {},
            "relationship_edges": [],
            "validation": {
                "complete": True,
                "eligible_state_count": 0,
                "unique_state_count_in_tour": 0,
                "tour_step_count": 0,
                "missing_state_ids": [],
                "disconnected_state_ids": [],
                "disconnected_transitions": [],
                "bounded_transitions": [],
                "unplaced_state_ids": [],
                "placement_ready": True,
                "tour_bounded": True,
                "max_tour_steps": 0,
            },
        }

    resolved_anchor = _value(anchor_state_id)
    if resolved_anchor not in state_by_id:
        resolved_anchor = state_ids[0]

    state_id_by_member_id = {
        _value(state.get("member_id")): state_id
        for state_id, state in state_by_id.items()
        if _value(state.get("member_id"))
    }
    navigation: dict[str, dict[str, set[str]]] = {
        state_id: {
            "parents": set(),
            "children": set(),
            "partners": set(),
            "siblings": set(),
            "branches": set(),
        }
        for state_id in state_ids
    }
    adjacency: dict[str, set[str]] = {state_id: set() for state_id in state_ids}
    relationship_edges: list[dict[str, Any]] = []
    all_children_by_parent_member: dict[str, set[str]] = defaultdict(set)

    def add_adjacency(source_state_id: str, target_state_id: str) -> None:
        if source_state_id == target_state_id:
            return
        adjacency[source_state_id].add(target_state_id)
        adjacency[target_state_id].add(source_state_id)

    active_relationships = sorted(
        (
            relationship
            for relationship in relationships
            if _relationship_is_active(relationship)
        ),
        key=lambda relationship: (
            _value(relationship.get("source_member_id")),
            _value(relationship.get("target_member_id")),
            normalize_relationship_type(relationship.get("relationship_type")),
            _value(relationship.get("relationship_mode")),
            _value(relationship.get("status_marker")),
            _value(relationship.get("_id") or relationship.get("id")),
        ),
    )

    for relationship in active_relationships:
        source_member_id = _value(relationship.get("source_member_id"))
        target_member_id = _value(relationship.get("target_member_id"))
        relationship_type = normalize_relationship_type(
            relationship.get("relationship_type")
        )
        if not source_member_id or not target_member_id:
            continue

        if relationship_type in _SIBLING_DERIVATION_PARENT_TYPES:
            all_children_by_parent_member[source_member_id].add(target_member_id)

        source_state_id = state_id_by_member_id.get(source_member_id, "")
        target_state_id = state_id_by_member_id.get(target_member_id, "")
        if not source_state_id or not target_state_id or source_state_id == target_state_id:
            continue

        add_adjacency(source_state_id, target_state_id)
        if relationship_type in _DIRECT_ANCESTRY_TYPES:
            navigation[source_state_id]["children"].add(target_state_id)
            navigation[target_state_id]["parents"].add(source_state_id)
        elif relationship_type in PARTNER_RELATIONSHIP_TYPES:
            navigation[source_state_id]["partners"].add(target_state_id)
            navigation[target_state_id]["partners"].add(source_state_id)
        elif relationship_type in SIBLING_RELATIONSHIP_TYPES:
            navigation[source_state_id]["siblings"].add(target_state_id)
            navigation[target_state_id]["siblings"].add(source_state_id)
        else:
            navigation[source_state_id]["branches"].add(target_state_id)
            navigation[target_state_id]["branches"].add(source_state_id)

        relationship_edges.append(
            {
                "source_state_id": source_state_id,
                "target_state_id": target_state_id,
                "relationship_type": relationship_type,
                "relationship_mode": _value(
                    relationship.get("relationship_mode")
                )
                or "narrative",
                "status_marker": _value(relationship.get("status_marker"))
                or "narrative",
                "privacy_scope": _value(relationship.get("privacy_scope"))
                or "household_private",
                "label": _relationship_label(relationship_type, relationship),
                "visual_style": _visual_style(relationship_type, relationship),
            }
        )

    # Two visible children of the same parent are siblings even when the parent
    # portrait is not approved and therefore has no cinematic state.
    for child_member_ids in all_children_by_parent_member.values():
        visible_sibling_states = sorted(
            {
                state_id_by_member_id[member_id]
                for member_id in child_member_ids
                if member_id in state_id_by_member_id
            },
            key=lambda item: _state_sort_key(state_by_id[item]),
        )
        for index, source_state_id in enumerate(visible_sibling_states):
            for target_state_id in visible_sibling_states[index + 1 :]:
                navigation[source_state_id]["siblings"].add(target_state_id)
                navigation[target_state_id]["siblings"].add(source_state_id)
                add_adjacency(source_state_id, target_state_id)

    def sorted_state_ids(values: set[str] | list[str]) -> list[str]:
        return sorted(
            {value for value in values if value in state_by_id},
            key=lambda item: _state_sort_key(state_by_id[item]),
        )

    ordered_targets: list[str] = []
    visit_reason: dict[str, str] = {}

    def add_target(state_id: str, reason: str) -> None:
        if state_id not in state_by_id or state_id in visit_reason:
            return
        visit_reason[state_id] = reason
        ordered_targets.append(state_id)

    add_target(resolved_anchor, "anchor")

    def visit_ancestors(state_id: str) -> None:
        stack = list(
            reversed(sorted_state_ids(navigation[state_id]["parents"]))
        )
        while stack:
            parent_state_id = stack.pop()
            if parent_state_id in visit_reason:
                continue
            add_target(parent_state_id, "ancestor")
            stack.extend(
                reversed(
                    sorted_state_ids(navigation[parent_state_id]["parents"])
                )
            )

    def visit_descendants(state_id: str, reason: str = "descendant") -> None:
        stack = list(
            reversed(sorted_state_ids(navigation[state_id]["children"]))
        )
        while stack:
            child_state_id = stack.pop()
            if child_state_id in visit_reason:
                continue
            add_target(child_state_id, reason)
            for partner_state_id in sorted_state_ids(
                navigation[child_state_id]["partners"]
            ):
                add_target(partner_state_id, "partner")
            stack.extend(
                reversed(
                    sorted_state_ids(navigation[child_state_id]["children"])
                )
            )

    visit_ancestors(resolved_anchor)
    for partner_state_id in sorted_state_ids(navigation[resolved_anchor]["partners"]):
        add_target(partner_state_id, "partner")
    visit_descendants(resolved_anchor)

    for sibling_state_id in sorted_state_ids(navigation[resolved_anchor]["siblings"]):
        if sibling_state_id in visit_reason:
            continue
        add_target(sibling_state_id, "sibling_branch")
        for partner_state_id in sorted_state_ids(
            navigation[sibling_state_id]["partners"]
        ):
            add_target(partner_state_id, "partner")
        visit_descendants(sibling_state_id, "sibling_descendant")

    # Narrative, cultural, and other extended branches are visited after the
    # primary lineage so they remain represented without changing ancestry.
    branch_scan_index = 0
    while branch_scan_index < len(ordered_targets):
        source_state_id = ordered_targets[branch_scan_index]
        for branch_state_id in sorted_state_ids(
            navigation[source_state_id]["branches"]
        ):
            add_target(branch_state_id, "extended_branch")
        branch_scan_index += 1

    for state_id in state_ids:
        add_target(state_id, "additional_family_member")

    def shortest_path(start_state_id: str, end_state_id: str) -> list[str]:
        if start_state_id == end_state_id:
            return [start_state_id]
        queue: deque[str] = deque([start_state_id])
        previous: dict[str, str | None] = {start_state_id: None}
        while queue:
            current_state_id = queue.popleft()
            for neighbor_state_id in sorted_state_ids(adjacency[current_state_id]):
                if neighbor_state_id in previous:
                    continue
                previous[neighbor_state_id] = current_state_id
                if neighbor_state_id == end_state_id:
                    path = [end_state_id]
                    cursor = current_state_id
                    while cursor is not None:
                        path.append(cursor)
                        cursor = previous[cursor]
                    return list(reversed(path))
                queue.append(neighbor_state_id)
        return []

    max_tour_steps = max(len(state_ids), len(state_ids) * 4)
    tour_state_ids: list[str] = [ordered_targets[0]]
    tour_reasons: list[str] = [visit_reason[ordered_targets[0]]]
    disconnected_transitions: list[dict[str, str]] = []
    bounded_transitions: list[dict[str, str]] = []

    remaining_targets = ordered_targets[1:]
    for target_index, target_state_id in enumerate(remaining_targets):
        if target_state_id in tour_state_ids:
            continue
        current_state_id = tour_state_ids[-1]
        path = shortest_path(current_state_id, target_state_id)
        additions = path[1:] if path else [target_state_id]
        if not path:
            disconnected_transitions.append(
                {"from_state_id": current_state_id, "to_state_id": target_state_id}
            )

        future_unseen_targets = {
            future_target
            for future_target in remaining_targets[target_index + 1 :]
            if future_target not in tour_state_ids and future_target != target_state_id
        }
        bridge_budget = max(
            0,
            max_tour_steps
            - len(tour_state_ids)
            - 1
            - len(future_unseen_targets),
        )
        if len(additions) > bridge_budget + 1:
            bounded_transitions.append(
                {"from_state_id": current_state_id, "to_state_id": target_state_id}
            )
            additions = [*additions[:bridge_budget], target_state_id]
        for addition in additions:
            if addition == tour_state_ids[-1]:
                continue
            tour_state_ids.append(addition)
            tour_reasons.append(
                visit_reason.get(addition, "bridge")
                if addition == target_state_id
                else "bridge"
            )

    seen_states: set[str] = set()
    tour_steps: list[dict[str, Any]] = []
    path_items: list[str] = []
    for index, (state_id, reason) in enumerate(zip(tour_state_ids, tour_reasons)):
        state = state_by_id[state_id]
        title = _value(state.get("title") or state.get("node")) or "Family Member"
        is_return = state_id in seen_states
        seen_states.add(state_id)
        step_id = f"tour-{index + 1:04d}-{state_id}"
        tour_steps.append(
            {
                "step_id": step_id,
                "state_id": state_id,
                "title": title,
                "generation": _coerce_generation(state.get("generation")),
                "reason": "return" if is_return else reason,
                "is_return": is_return,
                "previous_step_id": (
                    f"tour-{index:04d}-{tour_state_ids[index - 1]}"
                    if index > 0
                    else None
                ),
                "next_step_id": None,
            }
        )
        path_items.append(f"Return to {title}" if is_return else title)

    for index in range(len(tour_steps) - 1):
        tour_steps[index]["next_step_id"] = tour_steps[index + 1]["step_id"]

    option_prefixes = (
        ("parents", "Parent / ancestor"),
        ("children", "Child / descendant"),
        ("partners", "Partner"),
        ("siblings", "Sibling branch"),
        ("branches", "Family branch"),
    )
    branch_options_by_state: dict[str, list[dict[str, str]]] = {}
    navigation_by_state: dict[str, dict[str, list[str]]] = {}
    for state_id in state_ids:
        state_navigation = {
            key: sorted_state_ids(list(values))
            for key, values in navigation[state_id].items()
        }
        navigation_by_state[state_id] = state_navigation
        options: list[dict[str, str]] = []
        seen_targets: set[str] = set()
        for key, prefix in option_prefixes:
            for target_state_id in state_navigation[key]:
                if target_state_id in seen_targets:
                    continue
                seen_targets.add(target_state_id)
                target_title = _value(
                    state_by_id[target_state_id].get("title")
                    or state_by_id[target_state_id].get("node")
                )
                options.append(
                    {
                        "label": f"{prefix}: {target_title}",
                        "target_state_id": target_state_id,
                        "relationship_group": key,
                    }
                )
        branch_options_by_state[state_id] = options

    reachable: set[str] = set()
    queue = deque([resolved_anchor])
    while queue:
        current_state_id = queue.popleft()
        if current_state_id in reachable:
            continue
        reachable.add(current_state_id)
        queue.extend(adjacency[current_state_id] - reachable)

    missing_state_ids = sorted(set(state_ids) - set(tour_state_ids))
    disconnected_state_ids = sorted(set(state_ids) - reachable)
    unplaced_state_ids = sorted(
        state_id
        for state_id, state in state_by_id.items()
        if _value(state.get("placement_status")).lower()
        in {"unplaced", "conflict", "unresolved"}
    )
    validation = {
        "complete": not missing_state_ids,
        "eligible_state_count": len(state_ids),
        "unique_state_count_in_tour": len(set(tour_state_ids)),
        "tour_step_count": len(tour_steps),
        "missing_state_ids": missing_state_ids,
        "disconnected_state_ids": disconnected_state_ids,
        "disconnected_transitions": disconnected_transitions,
        "bounded_transitions": bounded_transitions,
        "unplaced_state_ids": unplaced_state_ids,
        "placement_ready": not unplaced_state_ids,
        "tour_bounded": len(tour_steps) <= max_tour_steps,
        "max_tour_steps": max_tour_steps,
    }

    return {
        "compiler_version": LINEAGE_CINEMA_COMPILER_VERSION,
        "anchor_state_id": resolved_anchor,
        "ordered_state_ids": ordered_targets,
        "tour_steps": tour_steps,
        "auto_advance_state_ids": tour_state_ids,
        "path_items": path_items,
        "branch_options_by_state": branch_options_by_state,
        "navigation_by_state": navigation_by_state,
        "relationship_edges": relationship_edges,
        "validation": validation,
    }


__all__ = [
    "LINEAGE_CINEMA_COMPILER_VERSION",
    "compile_lineage_cinema",
]
