import datetime
import hashlib
from collections import deque
from typing import Any, Dict, List, Optional, Set

from app.database import get_database


def _member_identifier(member: Dict[str, Any]) -> str:
    custom_id = member.get("id")
    if custom_id:
        return str(custom_id)

    mongo_id = member.get("_id")
    if mongo_id is not None:
        return str(mongo_id)

    return ""


def _extract_member_name(member: Dict[str, Any]) -> str:
    if member.get("name"):
        return str(member.get("name")).strip()

    first_name = str(member.get("first_name", "") or "").strip()
    middle_name = str(member.get("middle_name", "") or "").strip()
    last_name = str(member.get("last_name", "") or "").strip()

    full_name = " ".join(part for part in [first_name, middle_name, last_name] if part).strip()
    if full_name:
        return full_name

    return "Unknown"


def _normalize_relationship_type(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _build_member_map(members: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    member_map: Dict[str, Dict[str, Any]] = {}

    for member in members:
        member_id = _member_identifier(member)
        if member_id:
            member_map[member_id] = member

    return member_map


def _build_parent_to_children_map(relationships: List[Dict[str, Any]]) -> Dict[str, Set[str]]:
    parent_to_children: Dict[str, Set[str]] = {}

    for relationship in relationships:
        relationship_type = _normalize_relationship_type(
            relationship.get("relationship_type") or relationship.get("type")
        )

        source_member_id = relationship.get("source_member_id")
        target_member_id = relationship.get("target_member_id")
        from_member_id = relationship.get("from_member_id") or relationship.get("member_1_id")
        to_member_id = relationship.get("to_member_id") or relationship.get("member_2_id")

        left_id = str(source_member_id or from_member_id or "")
        right_id = str(target_member_id or to_member_id or "")

        if not left_id or not right_id:
            continue

        if relationship_type in {"parent", "father", "mother"}:
            parent_to_children.setdefault(left_id, set()).add(right_id)

        elif relationship_type in {"child", "son", "daughter"}:
            parent_to_children.setdefault(right_id, set()).add(left_id)

    return parent_to_children


def _find_descendant_path(
    ancestor_id: str,
    descendant_id: str,
    parent_to_children: Dict[str, Set[str]],
) -> Optional[List[str]]:
    if ancestor_id == descendant_id:
        return [ancestor_id]

    queue = deque([(ancestor_id, [ancestor_id])])
    visited: Set[str] = set()

    while queue:
        current_id, path = queue.popleft()

        if current_id in visited:
            continue

        visited.add(current_id)

        for child_id in sorted(parent_to_children.get(current_id, set())):
            if child_id == descendant_id:
                return path + [child_id]

            if child_id not in visited:
                queue.append((child_id, path + [child_id]))

    return None


def generate_lineage_proof(
    family_id: str,
    ancestor_id: str,
    descendant_id: str,
) -> Dict[str, Any]:
    db = get_database()
    if db is None:
        return {
            "success": False,
            "error": "Database connection is not available.",
        }

    members = list(db.family_members.find({"family_id": family_id}))
    relationships = list(db.relationships.find({}))

    member_map = _build_member_map(members)
    parent_to_children = _build_parent_to_children_map(relationships)

    if ancestor_id not in member_map:
        return {
            "success": False,
            "error": "Ancestor not found in this family.",
            "available_member_ids": sorted(member_map.keys()),
        }

    if descendant_id not in member_map:
        return {
            "success": False,
            "error": "Descendant not found in this family.",
            "available_member_ids": sorted(member_map.keys()),
        }

    path_ids = _find_descendant_path(ancestor_id, descendant_id, parent_to_children)

    if not path_ids:
        return {
            "success": False,
            "proof_exists": False,
            "message": "No descendant path found between the supplied members.",
            "family_id": family_id,
            "ancestor_id": ancestor_id,
            "descendant_id": descendant_id,
            "available_member_ids": sorted(member_map.keys()),
        }

    path_members = []
    for member_id in path_ids:
        member = member_map[member_id]
        path_members.append(
            {
                "id": member_id,
                "name": _extract_member_name(member),
            }
        )

    generated_at = datetime.datetime.utcnow().isoformat()
    hash_source = (
        f"{family_id}|"
        f"{ancestor_id}|"
        f"{descendant_id}|"
        f"{'->'.join(path_ids)}|"
        f"{generated_at}"
    )
    proof_hash = hashlib.sha256(hash_source.encode()).hexdigest()

    return {
        "success": True,
        "proof_exists": True,
        "proof_type": "descendant_path",
        "family_id": family_id,
        "ancestor": {
            "id": ancestor_id,
            "name": _extract_member_name(member_map[ancestor_id]),
        },
        "descendant": {
            "id": descendant_id,
            "name": _extract_member_name(member_map[descendant_id]),
        },
        "path_length": len(path_ids),
        "path": path_members,
        "proof_hash": proof_hash,
        "generated_at": generated_at,
    }