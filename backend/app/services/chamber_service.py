from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.database import get_database
from app.services.access_context_service import build_access_context
from app.services.experience_state_service import get_experience_session, get_recommended_next_step
from app.services.lineage_chamber_service import build_lineage_chamber_summary
from app.services.narrative_service import build_experience_story
from app.services.presence_service import build_presence_overview
from app.services.workspace_access_service import resolve_workspace_context


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


def build_experience_chamber(current_user: dict[str, Any], project_id: str) -> dict[str, Any]:
    context = resolve_workspace_context(current_user, project_id=project_id)
    project = context.get("project") or {}
    family = context.get("family") or {}
    access_context = build_access_context(current_user, project_id=project_id)
    experience_session = get_experience_session(current_user, project_id=project_id)
    recommended_next = get_recommended_next_step(current_user, project_id=project_id)

    family_id = _normalize(family.get("_id"))
    if family_id:
        db = get_database()
        family_lookup = {"family_id": {"$in": _family_lookup_values(family_id)}}
        uploads = list(db["uploaded_files"].find(family_lookup))
        lineage_summary = build_lineage_chamber_summary(family_id)
        narrative_summary = build_experience_story(family_id)
        archive_summary = {
            "asset_count": len(uploads),
            "portrait_count": len([upload for upload in uploads if upload.get("category") == "member_photo"]),
            "verification_asset_count": len([upload for upload in uploads if upload.get("category") == "verification_evidence"]),
        }
        trust_summary = lineage_summary["trust_state"]
        certificate_readiness = {
            "ready": bool(trust_summary.get("certificate_ready")),
            "verified_records": trust_summary.get("verified_records", 0),
            "contradictory_records": trust_summary.get("contradictory_records", 0),
        }
        featured_family = {
            "family_id": lineage_summary["family_id"],
            "family_name": lineage_summary["family_name"],
            "featured_branch": (lineage_summary["branch_summary"] or [{}])[0],
        }
    else:
        lineage_summary = {
            "family_id": None,
            "family_name": "Legacy chamber not yet anchored",
            "branch_summary": [],
            "trust_state": {
                "member_count": 0,
                "relationship_count": 0,
                "verified_records": 0,
                "pending_records": 0,
                "contradictory_records": 0,
                "certificate_ready": False,
            },
        }
        narrative_summary = {
            "opening_summary": "The chamber is prepared for the first anchored family branch.",
            "key_lineage_branches": [],
            "major_verified_milestones": [],
            "unresolved_mysteries": ["Create a family root to begin the living archive."],
            "important_descendants": [],
            "recommended_next_path": "Anchor the first family chamber.",
            "archive_highlights": [],
            "certificate_progress": lineage_summary["trust_state"],
        }
        archive_summary = {
            "asset_count": 0,
            "portrait_count": 0,
            "verification_asset_count": 0,
        }
        trust_summary = lineage_summary["trust_state"]
        certificate_readiness = {
            "ready": False,
            "verified_records": 0,
            "contradictory_records": 0,
        }
        featured_family = {
            "family_id": None,
            "family_name": "Legacy chamber not yet anchored",
            "featured_branch": {},
        }

    live_presence = build_presence_overview(
        project_id=_normalize(project.get("_id")),
        family_id=family_id,
    )

    return {
        "user_identity_summary": {
            "user_id": access_context["user_id"],
            "email": access_context["email"],
            "role": access_context["role"],
            "mode": access_context["experience_mode"],
        },
        "project_lane": access_context["package_lane"],
        "current_chamber": experience_session["current_chamber"],
        "featured_family": featured_family,
        "lineage_summary": lineage_summary,
        "archive_summary": archive_summary,
        "trust_summary": trust_summary,
        "certificate_readiness": certificate_readiness,
        "narrative_summary": narrative_summary,
        "live_presence": live_presence,
        "recommended_next_transition": recommended_next,
        "unlocked_modules": access_context["allowed_experience_modules"],
    }
