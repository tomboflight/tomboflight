from app.database import get_database


def _serialize_member(member: dict) -> dict:
    return {
        "id": str(member["_id"]),
        "family_id": member.get("family_id"),
        "household_id": member.get("household_id"),
        "network_id": member.get("network_id"),
        "first_name": member.get("first_name"),
        "last_name": member.get("last_name"),
        "full_name": f"{member.get('first_name', '')} {member.get('last_name', '')}".strip(),
        "birth_year": member.get("birth_year"),
        "generation": member.get("generation"),
        "father_id": member.get("father_id"),
        "mother_id": member.get("mother_id"),
        "spouse_id": member.get("spouse_id"),
        "bio": member.get("bio"),
        "privacy_marker": member.get("privacy_marker"),
        "created_at": member.get("created_at"),
    }


def _serialize_node(node: dict) -> dict:
    return {
        "id": str(node["_id"]),
        "family_id": node.get("family_id"),
        "member_id": node.get("member_id"),
        "generation": node.get("generation"),
        "x": node.get("x", 0),
        "y": node.get("y", 0),
        "parent_node_ids": node.get("parent_node_ids", []),
        "child_node_ids": node.get("child_node_ids", []),
        "created_at": node.get("created_at"),
    }


def _serialize_relationship(rel: dict) -> dict:
    return {
        "id": str(rel["_id"]),
        "source_member_id": rel.get("source_member_id"),
        "target_member_id": rel.get("target_member_id"),
        "relationship_type": rel.get("relationship_type"),
        "relationship_mode": rel.get("relationship_mode"),
        "status_marker": rel.get("status_marker"),
        "notes": rel.get("notes"),
        "created_at": rel.get("created_at"),
    }


def _build_edges(relationships: list[dict]) -> list[dict]:
    edges = []
    for rel in relationships:
        edges.append(
            {
                "source": rel.get("source_member_id"),
                "target": rel.get("target_member_id"),
                "relationship_type": rel.get("relationship_type"),
                "relationship_mode": rel.get("relationship_mode"),
                "status_marker": rel.get("status_marker"),
            }
        )
    return edges


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

    family = db.families.find_one({"_id": family_id})
    if family is None:
        family = db.families.find_one({"family_name": family_id})

    members = list(db.family_members.find({"family_id": family_id}))
    nodes = list(db.lineage_nodes.find({"family_id": family_id}))
    relationships = list(db.relationships.find())

    member_ids = {str(member["_id"]) for member in members}
    filtered_relationships = [
        rel
        for rel in relationships
        if rel.get("source_member_id") in member_ids or rel.get("target_member_id") in member_ids
    ]

    return {
        "family_id": family_id,
        "mode": "default",
        "family": family,
        "members": [_serialize_member(member) for member in members],
        "nodes": [_serialize_node(node) for node in nodes],
        "relationships": [_serialize_relationship(rel) for rel in filtered_relationships],
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

    family = db.families.find_one({"_id": family_id})
    if family is None:
        family = db.families.find_one({"family_name": family_id})

    members = list(db.family_members.find({"family_id": family_id}))
    nodes = list(db.lineage_nodes.find({"family_id": family_id}))
    relationships = list(db.relationships.find())

    member_ids = {str(member["_id"]) for member in members}
    relationships = [
        rel
        for rel in relationships
        if rel.get("source_member_id") in member_ids or rel.get("target_member_id") in member_ids
    ]

    if mode == "verified":
        allowed_markers = {"Verified"}
        allowed_modes = {"verified"}
    elif mode == "narrative":
        allowed_markers = {"Verified", "Narrative"}
        allowed_modes = {"verified", "narrative"}
    elif mode == "private":
        allowed_markers = {"Verified", "Narrative", "Private", "Unknown"}
        allowed_modes = {"verified", "narrative", "private", "unknown"}
    else:
        allowed_markers = {"Verified", "Narrative", "Private", "Unknown"}
        allowed_modes = {"verified", "narrative", "private", "unknown"}

    filtered_relationships = [
        rel
        for rel in relationships
        if rel.get("status_marker") in allowed_markers
        or rel.get("relationship_mode") in allowed_modes
    ]

    connected_member_ids = set()
    for rel in filtered_relationships:
        if rel.get("source_member_id"):
            connected_member_ids.add(rel["source_member_id"])
        if rel.get("target_member_id"):
            connected_member_ids.add(rel["target_member_id"])

    filtered_members = [
        member for member in members if str(member["_id"]) in connected_member_ids
    ]

    filtered_nodes = [
        node for node in nodes if node.get("member_id") in connected_member_ids
    ]

    return {
        "family_id": family_id,
        "mode": mode,
        "family": family,
        "members": [_serialize_member(member) for member in filtered_members],
        "nodes": [_serialize_node(node) for node in filtered_nodes],
        "relationships": [_serialize_relationship(rel) for rel in filtered_relationships],
        "edges": _build_edges(filtered_relationships),
    }