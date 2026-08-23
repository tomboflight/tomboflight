from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.core.relationship_catalog import (
    PARENT_RELATIONSHIP_TYPES,
    normalize_relationship_type,
    relationship_generation_delta,
)


class FamilyPlacementError(ValueError):
    pass


def _value(value: Any) -> str:
    return str(value or "").strip()


def _member_id(document: dict[str, Any]) -> str:
    return _value(document.get("_id") or document.get("id") or document.get("member_id"))


def _family_candidates(family_id: str) -> list[Any]:
    values: list[Any] = [family_id]
    if ObjectId.is_valid(family_id):
        values.append(ObjectId(family_id))
    return values


def _constraints(
    relationships: list[dict[str, Any]],
) -> list[tuple[str, str, int, str]]:
    result: list[tuple[str, str, int, str]] = []
    for relationship in relationships:
        source_id = _value(relationship.get("source_member_id"))
        target_id = _value(relationship.get("target_member_id"))
        relationship_type = normalize_relationship_type(
            relationship.get("relationship_type")
        )
        delta = relationship_generation_delta(relationship_type)
        if not source_id or not target_id or delta is None:
            continue
        result.append((source_id, target_id, delta, relationship_type))
    return result


def calculate_family_placement(
    db: Any,
    family_id: str,
    *,
    extra_relationship: dict[str, Any] | None = None,
) -> dict[str, Any]:
    members = list(
        db["family_members"].find(
            {"family_id": {"$in": _family_candidates(family_id)}}
        )
    )
    member_by_id = {
        _member_id(member): member for member in members if _member_id(member)
    }
    relationships = list(
        db["relationships"].find(
            {"family_id": {"$in": _family_candidates(family_id)}}
        )
    )
    if extra_relationship:
        relationships.append(dict(extra_relationship))

    constraints = _constraints(relationships)
    adjacency: dict[str, list[tuple[str, int]]] = {
        member_id: [] for member_id in member_by_id
    }
    for source_id, target_id, delta, _relationship_type in constraints:
        if source_id not in member_by_id or target_id not in member_by_id:
            continue
        adjacency[source_id].append((target_id, delta))
        adjacency[target_id].append((source_id, -delta))

    assignments: dict[str, int] = {}
    placement_status: dict[str, str] = {}
    visited: set[str] = set()

    for seed_id in sorted(member_by_id):
        if seed_id in visited:
            continue
        component: list[str] = []
        relative: dict[str, int] = {seed_id: 0}
        queue: deque[str] = deque([seed_id])

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            for neighbor, delta in adjacency.get(current, []):
                expected = relative[current] + delta
                if neighbor in relative and relative[neighbor] != expected:
                    raise FamilyPlacementError(
                        "Relationship placement conflict: the selected links require "
                        "the same person to occupy two different generations."
                    )
                if neighbor not in relative:
                    relative[neighbor] = expected
                    queue.append(neighbor)

        has_structure = any(adjacency.get(member_id) for member_id in component)
        locked_offsets: set[int] = set()
        for member_id in component:
            member = member_by_id[member_id]
            if not bool(member.get("generation_locked")):
                continue
            try:
                locked_generation = int(member.get("generation"))
            except (TypeError, ValueError):
                continue
            locked_offsets.add(locked_generation - relative[member_id])

        if len(locked_offsets) > 1:
            raise FamilyPlacementError(
                "Locked generation values conflict with the selected family relationships."
            )

        if locked_offsets:
            offset = next(iter(locked_offsets))
        elif has_structure:
            offset = -min(relative.values())
        elif len(member_by_id) == 1:
            offset = 0
        else:
            offset = 0

        for member_id in component:
            generation = relative[member_id] + offset
            if generation < 0:
                raise FamilyPlacementError(
                    "Relationship placement would create a negative generation."
                )
            member = member_by_id[member_id]
            if has_structure or len(member_by_id) == 1 or bool(member.get("generation_locked")):
                assignments[member_id] = generation
                placement_status[member_id] = (
                    "root" if len(member_by_id) == 1 and not has_structure else "placed"
                )
            else:
                try:
                    assignments[member_id] = max(0, int(member.get("generation") or 0))
                except (TypeError, ValueError):
                    assignments[member_id] = 0
                placement_status[member_id] = "unplaced"

    return {
        "family_id": family_id,
        "assignments": assignments,
        "placement_status": placement_status,
        "constraints": constraints,
        "members": member_by_id,
    }


def _find_lineage_node(db: Any, family_id: str, member_id: str) -> dict[str, Any] | None:
    return db["lineage_nodes"].find_one(
        {
            "family_id": {"$in": _family_candidates(family_id)},
            "member_id": member_id,
        }
    )


def rebuild_family_placement(db: Any, family_id: str) -> dict[str, Any]:
    placement = calculate_family_placement(db, family_id)
    assignments: dict[str, int] = placement["assignments"]
    statuses: dict[str, str] = placement["placement_status"]
    now = datetime.now(UTC).isoformat()

    by_generation: dict[int, list[str]] = {}
    for member_id, generation in assignments.items():
        by_generation.setdefault(generation, []).append(member_id)

    coordinates: dict[str, tuple[float, float]] = {}
    for generation, member_ids in by_generation.items():
        for row, member_id in enumerate(sorted(member_ids)):
            coordinates[member_id] = (float(generation * 360), float(row * 180))

    for member_id, generation in assignments.items():
        db["family_members"].update_one(
            {"_id": ObjectId(member_id) if ObjectId.is_valid(member_id) else member_id},
            {
                "$set": {
                    "generation": generation,
                    "placement_status": statuses.get(member_id, "unplaced"),
                    "placement_basis": "relationships",
                    "placement_updated_at": now,
                    "updated_at": now,
                }
            },
        )
        x, y = coordinates.get(member_id, (float(generation * 360), 0.0))
        node_payload = {
            "family_id": family_id,
            "member_id": member_id,
            "generation": generation,
            "x": x,
            "y": y,
            "parent_node_ids": [],
            "child_node_ids": [],
            "placement_status": statuses.get(member_id, "unplaced"),
            "updated_at": now,
        }
        existing = _find_lineage_node(db, family_id, member_id)
        if existing:
            db["lineage_nodes"].update_one(
                {"_id": existing["_id"]},
                {"$set": node_payload},
            )
        else:
            node_payload["created_at"] = now
            db["lineage_nodes"].insert_one(node_payload)

    node_by_member: dict[str, dict[str, Any]] = {}
    for member_id in assignments:
        node = _find_lineage_node(db, family_id, member_id)
        if node:
            node_by_member[member_id] = node

    parent_nodes: dict[str, set[str]] = {member_id: set() for member_id in assignments}
    child_nodes: dict[str, set[str]] = {member_id: set() for member_id in assignments}
    for source_id, target_id, _delta, relationship_type in placement["constraints"]:
        if relationship_type not in PARENT_RELATIONSHIP_TYPES:
            continue
        source_node = node_by_member.get(source_id)
        target_node = node_by_member.get(target_id)
        if not source_node or not target_node:
            continue
        child_nodes[source_id].add(_value(target_node.get("_id")))
        parent_nodes[target_id].add(_value(source_node.get("_id")))

    for member_id, node in node_by_member.items():
        db["lineage_nodes"].update_one(
            {"_id": node["_id"]},
            {
                "$set": {
                    "parent_node_ids": sorted(parent_nodes.get(member_id, set())),
                    "child_node_ids": sorted(child_nodes.get(member_id, set())),
                    "updated_at": now,
                }
            },
        )

    return {
        "family_id": family_id,
        "assigned_count": len(assignments),
        "unplaced_member_ids": sorted(
            member_id
            for member_id, marker in statuses.items()
            if marker == "unplaced"
        ),
        "generations": assignments,
    }

