from bson import ObjectId

from app.database import get_database
from app.schemas.graph_integrity import GraphIntegrityResponse, GraphIssue


def _get_family_document(db, family_id: str) -> dict | None:
    family = None

    if ObjectId.is_valid(family_id):
        family = db["families"].find_one({"_id": ObjectId(family_id)})

    if family is None:
        family = db["families"].find_one({"family_id": family_id})

    return family


def _normalize_member_id(member: dict) -> str:
    member_id = member.get("member_id")
    if isinstance(member_id, str) and member_id.strip():
        return member_id.strip()
    return str(member.get("_id", ""))


def _normalize_relationship_endpoint(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def analyze_family_graph_integrity(family_id: str) -> GraphIntegrityResponse:
    db = get_database()

    if db is None:
        raise ValueError("Database is not connected.")

    family = _get_family_document(db, family_id)
    if family is None:
        raise ValueError(f"Family not found: {family_id}")

    resolved_family_id = str(family.get("_id"))
    family_name = family.get("family_name") or family.get("name")

    members_cursor = db["family_members"].find({"family_id": resolved_family_id})
    relationships_cursor = db["relationships"].find({"family_id": resolved_family_id})

    members = list(members_cursor)
    relationships = list(relationships_cursor)

    member_ids: set[str] = set()
    member_lookup: dict[str, dict] = {}

    for member in members:
        normalized_id = _normalize_member_id(member)
        member_ids.add(normalized_id)
        member_lookup[normalized_id] = member

    issues: list[GraphIssue] = []
    connected_member_ids: set[str] = set()
    seen_edges: set[tuple[str, str, str]] = set()

    for relationship in relationships:
        source_id = _normalize_relationship_endpoint(relationship.get("source_id"))
        target_id = _normalize_relationship_endpoint(relationship.get("target_id"))
        relationship_type = str(relationship.get("relationship_type", "")).strip()

        if not source_id:
            issues.append(
                GraphIssue(
                    issue_type="missing_source_id",
                    message="Relationship is missing source_id.",
                    record={
                        "relationship_id": str(relationship.get("_id")),
                        "relationship_type": relationship_type,
                    },
                )
            )

        if not target_id:
            issues.append(
                GraphIssue(
                    issue_type="missing_target_id",
                    message="Relationship is missing target_id.",
                    record={
                        "relationship_id": str(relationship.get("_id")),
                        "relationship_type": relationship_type,
                    },
                )
            )

        if source_id and source_id not in member_ids:
            issues.append(
                GraphIssue(
                    issue_type="source_member_missing",
                    message="Relationship source_id does not match any family member.",
                    record={
                        "relationship_id": str(relationship.get("_id")),
                        "source_id": source_id,
                        "target_id": target_id,
                        "relationship_type": relationship_type,
                    },
                )
            )

        if target_id and target_id not in member_ids:
            issues.append(
                GraphIssue(
                    issue_type="target_member_missing",
                    message="Relationship target_id does not match any family member.",
                    record={
                        "relationship_id": str(relationship.get("_id")),
                        "source_id": source_id,
                        "target_id": target_id,
                        "relationship_type": relationship_type,
                    },
                )
            )

        if source_id and target_id and source_id == target_id:
            issues.append(
                GraphIssue(
                    issue_type="self_relationship",
                    message="Relationship links a member to itself.",
                    record={
                        "relationship_id": str(relationship.get("_id")),
                        "source_id": source_id,
                        "target_id": target_id,
                        "relationship_type": relationship_type,
                    },
                )
            )

        if source_id and target_id:
            connected_member_ids.add(source_id)
            connected_member_ids.add(target_id)

            edge_key = (source_id, target_id, relationship_type)
            if edge_key in seen_edges:
                issues.append(
                    GraphIssue(
                        issue_type="duplicate_relationship",
                        message="Duplicate relationship detected.",
                        record={
                            "relationship_id": str(relationship.get("_id")),
                            "source_id": source_id,
                            "target_id": target_id,
                            "relationship_type": relationship_type,
                        },
                    )
                )
            else:
                seen_edges.add(edge_key)

    isolated_member_ids = sorted(member_ids - connected_member_ids)

    for isolated_member_id in isolated_member_ids:
        member = member_lookup.get(isolated_member_id, {})
        issues.append(
            GraphIssue(
                issue_type="isolated_member",
                message="Member has no graph relationships.",
                record={
                    "member_id": isolated_member_id,
                    "full_name": member.get("full_name"),
                },
            )
        )

    return GraphIntegrityResponse(
        family_id=resolved_family_id,
        family_name=family_name,
        member_count=len(members),
        relationship_count=len(relationships),
        isolated_member_ids=isolated_member_ids,
        issues=issues,
        is_healthy=len(issues) == 0,
    )