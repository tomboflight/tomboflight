from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from bson import ObjectId

from app.database import get_database
from app.services.graph_integrity_service import analyze_family_graph_integrity


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _normalize_status(value: Any) -> str:
    return _normalize(value).lower()


def _family_lookup_values(family_id: str, resolved_family_id: str) -> list[Any]:
    values: list[Any] = []
    for candidate in {family_id, resolved_family_id}:
        normalized = _normalize(candidate)
        if not normalized:
            continue
        values.append(normalized)
        if ObjectId.is_valid(normalized):
            values.append(ObjectId(normalized))
    return values


def _find_family_document(db: Any, family_id: str) -> dict[str, Any] | None:
    if ObjectId.is_valid(family_id):
        family = db["families"].find_one({"_id": ObjectId(family_id)})
        if family is not None:
            return family
    return db["families"].find_one({"family_id": family_id})


def _member_display_name(member: dict[str, Any]) -> str:
    full_name = _normalize(member.get("full_name") or member.get("name"))
    if full_name:
        return full_name
    first_name = _normalize(member.get("first_name"))
    last_name = _normalize(member.get("last_name"))
    joined = f"{first_name} {last_name}".strip()
    return joined or "Unknown member"


def build_lineage_chamber_summary(family_id: str) -> dict[str, Any]:
    db = get_database()
    family = _find_family_document(db, family_id)
    if family is None:
        raise ValueError("Family not found.")

    resolved_family_id = _normalize(family.get("_id") or family_id)
    family_values = _family_lookup_values(family_id, resolved_family_id)
    family_filter = {"$in": family_values}

    members = list(db["family_members"].find({"family_id": family_filter}))
    relationships = list(db["relationships"].find({"family_id": family_filter}))
    uploads = list(db["uploaded_files"].find({"family_id": family_filter}))
    verification_records = list(db["verification_records"].find({"family_id": family_filter}))
    narrative_records = list(db["narrative_records"].find({"family_id": family_filter}))
    households = list(db["households"].find({"family_id": family_filter}))
    match_candidates = list(db["match_candidates"].find({"family_id": family_filter}))

    member_ids = {_normalize(member.get("_id")) for member in members}
    connected_member_ids: set[str] = set()
    for relationship in relationships:
        source_id = _normalize(
            relationship.get("source_member_id") or relationship.get("source_id") or relationship.get("person_1_id")
        )
        target_id = _normalize(
            relationship.get("target_member_id") or relationship.get("target_id") or relationship.get("person_2_id")
        )
        if source_id:
            connected_member_ids.add(source_id)
        if target_id:
            connected_member_ids.add(target_id)

    verified_statuses = {"verified", "approved", "complete", "completed"}
    pending_statuses = {"pending", "queued", "submitted", "under_review", "in_review"}
    contradictory_statuses = {"rejected", "contradicted", "disputed", "needs_revision"}

    verified_record_count = 0
    pending_record_count = 0
    contradictory_record_count = 0
    for record in verification_records:
        status_value = _normalize_status(record.get("status") or record.get("review_status"))
        if status_value in verified_statuses:
            verified_record_count += 1
        elif status_value in contradictory_statuses:
            contradictory_record_count += 1
        elif status_value in pending_statuses or not status_value:
            pending_record_count += 1

    verified_node_count = sum(
        1
        for member in members
        if bool(member.get("is_verified")) or _normalize(member.get("canonical_person_id"))
    )
    incomplete_nodes = [
        member
        for member in members
        if not _member_display_name(member)
        or not _normalize(member.get("birth_year") or member.get("birth_date"))
        or _normalize(member.get("_id")) not in connected_member_ids
    ]

    try:
        integrity_report = analyze_family_graph_integrity(resolved_family_id)
        orphaned_branches = len(integrity_report.isolated_member_ids)
    except Exception:
        orphaned_branches = max(0, len(member_ids - connected_member_ids))

    generation_counts: Counter[str] = Counter()
    youngest_generation_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for member in members:
        generation_key = _normalize(member.get("generation")) or "unassigned"
        generation_counts[generation_key] += 1
        youngest_generation_members[generation_key].append(member)

    branch_summary = [
        {
            "branch_key": generation_key,
            "member_count": count,
            "label": f"Generation {generation_key}" if generation_key != "unassigned" else "Unassigned branch",
        }
        for generation_key, count in generation_counts.most_common(5)
    ]

    pending_uploads = max(0, len(uploads) - verified_record_count)
    unresolved_identity_links = sum(
        1
        for candidate in match_candidates
        if _normalize_status(candidate.get("status") or "pending")
        in {"pending", "open", "needs_review", "candidate"}
    )

    narrative_ready_segments = min(
        len(branch_summary),
        len(narrative_records) + (1 if verified_node_count else 0),
    )
    certificate_ready_segments = 0
    if verified_record_count and contradictory_record_count == 0:
        certificate_ready_segments = max(1, min(len(branch_summary) or 1, verified_node_count or 1))

    certificate_ready = bool(
        members
        and relationships
        and verified_record_count > 0
        and contradictory_record_count == 0
        and unresolved_identity_links == 0
    )

    trust_state = {
        "member_count": len(members),
        "relationship_count": len(relationships),
        "household_count": len(households),
        "verified_records": verified_record_count,
        "pending_records": pending_record_count,
        "contradictory_records": contradictory_record_count,
        "certificate_ready": certificate_ready,
    }

    return {
        "family_id": resolved_family_id,
        "family_name": _normalize(family.get("family_name") or family.get("name")) or "Unnamed Family",
        "verified_nodes": verified_node_count,
        "incomplete_nodes": len(incomplete_nodes),
        "orphaned_branches": orphaned_branches,
        "narrative_ready_segments": narrative_ready_segments,
        "certificate_ready_segments": certificate_ready_segments,
        "pending_uploads": pending_uploads,
        "unresolved_identity_links": unresolved_identity_links,
        "trust_state": trust_state,
        "branch_summary": branch_summary,
    }
