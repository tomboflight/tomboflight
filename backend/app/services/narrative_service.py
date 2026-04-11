from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.database import get_database
from app.services.lineage_chamber_service import build_lineage_chamber_summary


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _family_lookup_values(family_id: str) -> list[Any]:
    values: list[Any] = []
    normalized = _normalize(family_id)
    if normalized:
        values.append(normalized)
        if ObjectId.is_valid(normalized):
            values.append(ObjectId(normalized))
    return values


def _member_display_name(member: dict[str, Any]) -> str:
    return (
        _normalize(member.get("full_name") or member.get("name"))
        or f"{_normalize(member.get('first_name'))} {_normalize(member.get('last_name'))}".strip()
        or "Unknown member"
    )


def build_experience_story(family_id: str) -> dict[str, Any]:
    db = get_database()
    lineage_summary = build_lineage_chamber_summary(family_id)
    family_values = _family_lookup_values(lineage_summary["family_id"])

    members = list(db["family_members"].find({"family_id": {"$in": family_values}}))
    uploads = list(db["uploaded_files"].find({"family_id": {"$in": family_values}}))
    narrative_records = list(db["narrative_records"].find({"family_id": {"$in": family_values}}))

    family_name = lineage_summary["family_name"]
    opening_summary = (
        f"Enter the {family_name} chamber with {lineage_summary['verified_nodes']} verified nodes, "
        f"{lineage_summary['pending_uploads']} pending archive items, and "
        f"{lineage_summary['unresolved_identity_links']} unresolved identity links."
    )

    major_verified_milestones: list[str] = []
    if lineage_summary["verified_nodes"]:
        major_verified_milestones.append(
            f"{lineage_summary['verified_nodes']} lineage nodes are already anchored in trust state."
        )
    if lineage_summary["trust_state"].get("verified_records"):
        major_verified_milestones.append(
            f"{lineage_summary['trust_state']['verified_records']} proof records are verified."
        )
    if not major_verified_milestones:
        major_verified_milestones.append("The family chamber is ready for its first verified path.")

    unresolved_mysteries: list[str] = []
    if lineage_summary["incomplete_nodes"]:
        unresolved_mysteries.append(
            f"{lineage_summary['incomplete_nodes']} members still need deeper lineage detail."
        )
    if lineage_summary["pending_uploads"]:
        unresolved_mysteries.append(
            f"{lineage_summary['pending_uploads']} archive artifacts still need verification binding."
        )
    if lineage_summary["unresolved_identity_links"]:
        unresolved_mysteries.append(
            f"{lineage_summary['unresolved_identity_links']} identity links remain unresolved."
        )
    if not unresolved_mysteries:
        unresolved_mysteries.append("No unresolved branch tensions are currently blocking the chamber.")

    sorted_members = sorted(
        members,
        key=lambda member: (
            int(member.get("generation")) if str(member.get("generation") or "").isdigit() else 999,
            _member_display_name(member).lower(),
        ),
    )
    important_descendants = [
        {
            "member_id": _normalize(member.get("_id")),
            "name": _member_display_name(member),
            "generation": member.get("generation"),
        }
        for member in sorted_members[:3]
    ]

    recommended_next_path = "Open the verification chamber to strengthen the next branch."
    if lineage_summary["trust_state"].get("certificate_ready"):
        recommended_next_path = "Move into the certificate chamber and crystallize the verified lineage."
    elif not uploads:
        recommended_next_path = "Seed the archive chamber with the first memory artifacts."
    elif not narrative_records:
        recommended_next_path = "Open the narrative chamber to assemble the first ceremonial story arc."

    archive_highlights = [
        f"{len(uploads)} archive artifacts are currently organized in the vault.",
        f"{len([upload for upload in uploads if upload.get('category') == 'member_photo'])} portrait assets are available.",
        f"{len([upload for upload in uploads if upload.get('category') == 'verification_evidence'])} proof assets are waiting in the archive.",
    ]

    return {
        "family_id": lineage_summary["family_id"],
        "opening_summary": opening_summary,
        "key_lineage_branches": lineage_summary["branch_summary"],
        "major_verified_milestones": major_verified_milestones,
        "unresolved_mysteries": unresolved_mysteries,
        "important_descendants": important_descendants,
        "recommended_next_path": recommended_next_path,
        "archive_highlights": archive_highlights,
        "certificate_progress": lineage_summary["trust_state"],
    }
