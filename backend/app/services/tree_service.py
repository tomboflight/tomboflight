from collections import deque
from datetime import date, datetime
from typing import Any

from bson import ObjectId

from app.core.relationship_catalog import normalize_relationship_type
from app.database import get_database


def _json_safe(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_safe(item) for item in value)
    return value


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _family_id_candidates(family_id: str) -> list[Any]:
    values: list[Any] = [family_id]
    if ObjectId.is_valid(family_id):
        values.append(ObjectId(family_id))
    return values


def _serialize_family(family: dict | None) -> dict | None:
    if not family:
        return None

    serialized = _json_safe(family)
    if (
        isinstance(serialized, dict)
        and serialized.get("_id")
        and not serialized.get("id")
    ):
        serialized["id"] = serialized["_id"]
    return serialized


def _serialize_member(member: dict) -> dict:
    return _json_safe(
        {
            "id": str(member.get("_id")),
            "family_id": _string_or_none(member.get("family_id")),
            "household_id": _string_or_none(member.get("household_id")),
            "network_id": _string_or_none(member.get("network_id")),
            "first_name": member.get("first_name"),
            "last_name": member.get("last_name"),
            "full_name": (
                f"{member.get('first_name', '')} {member.get('last_name', '')}"
            ).strip(),
            "birth_year": member.get("birth_year"),
            "generation": member.get("generation"),
            "father_id": _string_or_none(member.get("father_id")),
            "mother_id": _string_or_none(member.get("mother_id")),
            "spouse_id": _string_or_none(member.get("spouse_id")),
            "bio": member.get("bio"),
            "privacy_marker": member.get("privacy_marker"),
            "created_at": member.get("created_at"),
        }
    )


def _serialize_node(node: dict) -> dict:
    return _json_safe(
        {
            "id": str(node.get("_id")),
            "family_id": _string_or_none(node.get("family_id")),
            "member_id": _string_or_none(node.get("member_id")),
            "generation": node.get("generation"),
            "x": node.get("x", 0),
            "y": node.get("y", 0),
            "parent_node_ids": node.get("parent_node_ids", []),
            "child_node_ids": node.get("child_node_ids", []),
            "created_at": node.get("created_at"),
        }
    )


def _serialize_relationship(rel: dict) -> dict:
    return _json_safe(
        {
            "id": str(rel.get("_id")),
            "family_id": _string_or_none(rel.get("family_id")),
            "source_member_id": _string_or_none(rel.get("source_member_id")),
            "target_member_id": _string_or_none(rel.get("target_member_id")),
            "relationship_type": normalize_relationship_type(
                rel.get("relationship_type")
            ),
            "relationship_mode": rel.get("relationship_mode"),
            "status_marker": rel.get("status_marker"),
            "notes": rel.get("notes"),
            "created_at": rel.get("created_at"),
        }
    )


def _build_edges(relationships: list[dict]) -> list[dict]:
    edges = []
    for rel in relationships:
        edges.append(
            _json_safe(
                {
                    "source": _string_or_none(rel.get("source_member_id")),
                    "target": _string_or_none(rel.get("target_member_id")),
                    "relationship_type": normalize_relationship_type(
                        rel.get("relationship_type")
                    ),
                    "relationship_mode": rel.get("relationship_mode"),
                    "status_marker": rel.get("status_marker"),
                }
            )
        )
    return edges


def _relationship_touches_members(rel: dict, member_ids: set[str]) -> bool:
    return (
        _string_or_none(rel.get("source_member_id")) in member_ids
        or _string_or_none(rel.get("target_member_id")) in member_ids
    )


def _relationship_allowed_for_mode(rel: dict, mode: str) -> bool:
    normalized_mode = str(mode or "default").strip().lower()

    if normalized_mode == "verified":
        allowed_markers = {"verified"}
        allowed_modes = {"verified"}
    elif normalized_mode == "narrative":
        allowed_markers = {"verified", "narrative"}
        allowed_modes = {"verified", "narrative"}
    elif normalized_mode == "private":
        allowed_markers = {"verified", "narrative", "private", "unknown", ""}
        allowed_modes = {"verified", "narrative", "private", "unknown", ""}
    else:
        return True

    status_marker = str(rel.get("status_marker") or "").strip().lower()
    relationship_mode = str(rel.get("relationship_mode") or "").strip().lower()
    return status_marker in allowed_markers or relationship_mode in allowed_modes


def _find_family(db, family_id: str):
    if ObjectId.is_valid(family_id):
        family = db.families.find_one({"_id": ObjectId(family_id)})
        if family is not None:
            return family

    family = db.families.find_one({"family_id": family_id})
    if family is not None:
        return family

    family = db.families.find_one({"family_name": family_id})
    return family


def _find_members(db, family_id: str) -> list[dict]:
    candidates = _family_id_candidates(family_id)
    return list(db.family_members.find({"family_id": {"$in": candidates}}))


def _find_nodes(db, family_id: str) -> list[dict]:
    candidates = _family_id_candidates(family_id)
    return list(db.lineage_nodes.find({"family_id": {"$in": candidates}}))


def _find_relationships(db, family_id: str, member_ids: set[str]) -> list[dict]:
    candidates = _family_id_candidates(family_id)

    relationships = list(db.relationships.find({"family_id": {"$in": candidates}}))
    if relationships:
        return relationships

    if not member_ids:
        return []

    return list(
        db.relationships.find(
            {
                "$or": [
                    {"source_member_id": {"$in": list(member_ids)}},
                    {"target_member_id": {"$in": list(member_ids)}},
                ]
            }
        )
    )


def _find_family_household_id(db, family_id: str) -> str:
    family = _find_family(db, family_id) or {}
    return str(family.get("household_id") or "").strip()


def _linked_household_ids(db, household_id: str) -> set[str]:
    if not household_id:
        return set()
    queue = deque([household_id])
    visited: set[str] = set()

    while queue:
        current = queue.popleft()
        if not current or current in visited:
            continue
        visited.add(current)
        docs = list(
            db.household_links.find(
                {
                    "$or": [
                        {"source_household_id": current},
                        {"target_household_id": current},
                    ],
                    "link_status": "approved",
                }
            )
        )
        for doc in docs:
            source_id = str(doc.get("source_household_id") or "").strip()
            target_id = str(doc.get("target_household_id") or "").strip()
            if source_id and source_id not in visited:
                queue.append(source_id)
            if target_id and target_id not in visited:
                queue.append(target_id)

    return visited


def list_linked_family_ids(family_id: str) -> list[str]:
    db = get_database()
    if db is None:
        return [family_id]
    household_id = _find_family_household_id(db, family_id)
    if not household_id:
        return [family_id]

    household_ids = _linked_household_ids(db, household_id)
    if not household_ids:
        return [family_id]

    family_docs = list(
        db.families.find(
            {
                "household_id": {"$in": list(household_ids)},
            },
            {"_id": 1},
        )
    )
    family_ids = {str(item.get("_id")) for item in family_docs if item.get("_id")}
    if not family_ids:
        return [family_id]
    return sorted(family_ids)


def get_family_tree(family_id: str) -> dict:
    db = get_database()
    if db is None:
        return {
            "family_id": family_id,
            "mode": "default",
            "family": None,
            "members": [],
            "nodes": [],
            "relationships": [],
            "edges": [],
        }

    family = _find_family(db, family_id)
    members = _find_members(db, family_id)
    nodes = _find_nodes(db, family_id)

    member_ids = {str(member["_id"]) for member in members}
    relationships = _find_relationships(db, family_id, member_ids)

    filtered_relationships = [
        rel
        for rel in relationships
        if _relationship_touches_members(rel, member_ids)
    ]

    return {
        "family_id": family_id,
        "mode": "default",
        "family": _serialize_family(family),
        "members": [_serialize_member(member) for member in members],
        "nodes": [_serialize_node(node) for node in nodes],
        "relationships": [
            _serialize_relationship(rel) for rel in filtered_relationships
        ],
        "edges": _build_edges(filtered_relationships),
    }


def get_filtered_family_tree(family_id: str, mode: str) -> dict:
    db = get_database()
    if db is None:
        return {
            "family_id": family_id,
            "mode": mode,
            "family": None,
            "members": [],
            "nodes": [],
            "relationships": [],
            "edges": [],
        }

    family = _find_family(db, family_id)
    members = _find_members(db, family_id)
    nodes = _find_nodes(db, family_id)

    member_ids = {str(member["_id"]) for member in members}
    relationships = _find_relationships(db, family_id, member_ids)

    filtered_relationships = [
        rel
        for rel in relationships
        if _relationship_touches_members(rel, member_ids)
        and _relationship_allowed_for_mode(rel, mode)
    ]

    connected_member_ids = set()
    for rel in filtered_relationships:
        if rel.get("source_member_id"):
            connected_member_ids.add(str(rel["source_member_id"]))
        if rel.get("target_member_id"):
            connected_member_ids.add(str(rel["target_member_id"]))

    filtered_members = [
        member for member in members if str(member["_id"]) in connected_member_ids
    ]

    filtered_nodes = [
        node
        for node in nodes
        if _string_or_none(node.get("member_id")) in connected_member_ids
    ]

    return {
        "family_id": family_id,
        "mode": mode,
        "family": _serialize_family(family),
        "members": [_serialize_member(member) for member in filtered_members],
        "nodes": [_serialize_node(node) for node in filtered_nodes],
        "relationships": [
            _serialize_relationship(rel) for rel in filtered_relationships
        ],
        "edges": _build_edges(filtered_relationships),
    }


def get_linked_family_tree(family_id: str, mode: str = "default") -> dict:
    """Build a linked family graph spanning approved household links.

    Args:
        family_id: Root family identifier for the caller's workspace.
        mode: Graph filter mode. Supported values:
            - "default": all members/relationships from linked families
            - "verified": relationships marked verified
            - "narrative": verified + narrative relationships
            - "private": verified + narrative + private/unknown relationships

    Returns:
        A tree payload with members, nodes, relationships, edges, and linked_family_ids.
    """
    db = get_database()
    if db is None:
        return {
            "family_id": family_id,
            "mode": mode,
            "family": None,
            "members": [],
            "nodes": [],
            "relationships": [],
            "edges": [],
            "linked_family_ids": [],
        }

    linked_family_ids = list_linked_family_ids(family_id)
    if family_id not in linked_family_ids:
        linked_family_ids.insert(0, family_id)
    seen_family_ids = list(dict.fromkeys(linked_family_ids))

    members: list[dict] = []
    nodes: list[dict] = []
    relationships: list[dict] = []
    family = _find_family(db, family_id)
    member_ids: set[str] = set()

    for linked_family_id in seen_family_ids:
        linked_members = _find_members(db, linked_family_id)
        linked_nodes = _find_nodes(db, linked_family_id)
        members.extend(linked_members)
        nodes.extend(linked_nodes)
        member_ids.update(
            str(member.get("_id")) for member in linked_members if member.get("_id")
        )

    for linked_family_id in seen_family_ids:
        relationships.extend(_find_relationships(db, linked_family_id, member_ids))

    relationships = [
        rel
        for rel in relationships
        if _relationship_touches_members(rel, member_ids)
    ]

    if str(mode or "default").strip().lower() != "default":
        relationships = [
            rel
            for rel in relationships
            if _relationship_allowed_for_mode(rel, mode)
        ]
        connected_member_ids = set()
        for rel in relationships:
            if rel.get("source_member_id"):
                connected_member_ids.add(str(rel.get("source_member_id")))
            if rel.get("target_member_id"):
                connected_member_ids.add(str(rel.get("target_member_id")))
        members = [
            member
            for member in members
            if str(member.get("_id")) in connected_member_ids
        ]
        nodes = [
            node
            for node in nodes
            if _string_or_none(node.get("member_id")) in connected_member_ids
        ]

    return {
        "family_id": family_id,
        "mode": mode,
        "family": _serialize_family(family),
        "members": [_serialize_member(member) for member in members],
        "nodes": [_serialize_node(node) for node in nodes],
        "relationships": [
            _serialize_relationship(rel) for rel in relationships
        ],
        "edges": _build_edges(relationships),
        "linked_family_ids": seen_family_ids,
    }
