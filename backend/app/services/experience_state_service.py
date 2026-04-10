from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.database import get_database
from app.schemas.experience import ExperienceSessionStartRequest, ExperienceTransitionRequest
from app.services.access_context_service import resolve_default_project_id
from app.services.experience_catalog_service import (
    build_module_unlocks,
    chamber_label,
    derive_allowed_modules,
    get_lane_chambers,
)
from app.services.lineage_chamber_service import build_lineage_chamber_summary
from app.services.narrative_service import build_experience_story
from app.services.presence_service import build_presence_overview
from app.services.workspace_access_service import resolve_workspace_context


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _experience_collection():
    return get_database()["experience_sessions"]


def _resolve_context(current_user: dict[str, Any], project_id: str = "") -> dict[str, Any]:
    resolved_project_id = _normalize(project_id) or (resolve_default_project_id(current_user) or "")
    if not resolved_project_id:
        raise ValueError("No workspace project could be resolved for this user.")
    return resolve_workspace_context(current_user, project_id=resolved_project_id)


def _default_chamber(package_lane: str, family_exists: bool) -> str:
    lane_chambers = get_lane_chambers(package_lane)
    if package_lane == "portrait":
        return "portrait_chamber"
    if family_exists and "household_chamber" in lane_chambers:
        return "household_chamber"
    if family_exists and "network_chamber" in lane_chambers:
        return "network_chamber"
    if family_exists and "admin_workspace" in lane_chambers:
        return "admin_workspace"
    return lane_chambers[0]


def _load_session_document(user_id: str, project_id: str) -> dict[str, Any] | None:
    return _experience_collection().find_one(
        {"user_id": user_id, "project_id": project_id},
        sort=[("updated_at", -1)],
    )


def _family_snapshot(context: dict[str, Any]) -> dict[str, Any]:
    family = context.get("family") or {}
    if not family:
        return {
            "family_id": None,
            "family_name": "Legacy chamber not yet anchored",
            "member_count": 0,
        }

    summary = build_lineage_chamber_summary(_normalize(family.get("_id")))
    return {
        "family_id": summary["family_id"],
        "family_name": summary["family_name"],
        "member_count": summary["trust_state"].get("member_count", 0),
    }


def _build_checkpoints(context: dict[str, Any]) -> list[dict[str, Any]]:
    family = context.get("family") or {}
    if not family:
        return [
            {
                "key": "family_anchor",
                "label": "Anchor the family chamber",
                "completed": False,
                "detail": "Create the first family root to open lineage-aware chambers.",
            }
        ]

    summary = build_lineage_chamber_summary(_normalize(family.get("_id")))
    trust_state = summary["trust_state"]
    return [
        {
            "key": "family_anchor",
            "label": "Family chamber anchored",
            "completed": True,
            "detail": "The family chamber is linked to the active workspace.",
        },
        {
            "key": "lineage_mapping",
            "label": "Map the living branch",
            "completed": bool(trust_state.get("member_count")),
            "detail": f"{trust_state.get('member_count', 0)} members are currently mapped.",
        },
        {
            "key": "relationship_guardrails",
            "label": "Link relationships",
            "completed": bool(trust_state.get("relationship_count")),
            "detail": f"{trust_state.get('relationship_count', 0)} lineage relationships are active.",
        },
        {
            "key": "archive_seed",
            "label": "Seed the archive chamber",
            "completed": bool(trust_state.get("archive_asset_count")),
            "detail": f"{summary['pending_uploads']} archive items still need verification processing.",
        },
        {
            "key": "verification_trust",
            "label": "Establish trust state",
            "completed": bool(trust_state.get("verified_records")),
            "detail": f"{trust_state.get('verified_records', 0)} proof records are verified.",
        },
        {
            "key": "certificate_readiness",
            "label": "Reach certificate readiness",
            "completed": bool(trust_state.get("certificate_ready")),
            "detail": "Certificate readiness is active." if trust_state.get("certificate_ready") else "Resolve contradictions and complete proof depth to unlock issuance.",
        },
    ]


def _recommended_next_step(context: dict[str, Any]) -> dict[str, str]:
    family = context.get("family") or {}
    if not family:
        return {
            "chamber": "entry_chamber",
            "summary": "Anchor your first family chamber.",
            "reason": "A workspace root is required before lineage intelligence can unfold.",
        }

    summary = build_lineage_chamber_summary(_normalize(family.get("_id")))
    trust_state = summary["trust_state"]

    if not trust_state.get("relationship_count"):
        return {
            "chamber": "household_chamber",
            "summary": "Shape the household chamber.",
            "reason": "The lineage graph needs relationship links before deeper traversal can begin.",
        }
    if summary["pending_uploads"]:
        return {
            "chamber": "verification_chamber",
            "summary": "Review pending proof artifacts.",
            "reason": "Archive evidence is waiting to be converted into trust state.",
        }
    if not trust_state.get("verified_records"):
        return {
            "chamber": "archive_chamber",
            "summary": "Deepen the archive field.",
            "reason": "Additional documents are needed to establish a verified path.",
        }
    if not trust_state.get("certificate_ready"):
        return {
            "chamber": "narrative_chamber",
            "summary": "Assemble the next story arc.",
            "reason": "Narrative sequencing can reveal where the next legacy proof should focus.",
        }
    return {
        "chamber": "certificate_chamber",
        "summary": "Enter the certificate chamber.",
        "reason": "The family chamber is ready to crystallize into a formal legacy output.",
    }


def _allowed_transition_options(context: dict[str, Any], current_chamber: str) -> list[dict[str, Any]]:
    project = context.get("project") or {}
    entitlements = context.get("resolved_entitlements") or {}
    package_lane = _normalize(
        entitlements.get("package_lane") or project.get("project_lane") or "portrait"
    ).lower() or "portrait"
    allowed_modules = set(derive_allowed_modules(package_lane, entitlements))
    next_step = _recommended_next_step(context)

    options: list[dict[str, Any]] = []
    for chamber in get_lane_chambers(package_lane):
        unlocked = chamber == "entry_chamber" or context.get("is_admin") or chamber in allowed_modules
        reason = None if unlocked else "Locked by current package lane or entitlements."
        if chamber == current_chamber:
            continue
        option = {
            "chamber": chamber,
            "label": chamber_label(chamber),
            "unlocked": unlocked,
            "reason": reason,
        }
        if chamber == next_step["chamber"] and unlocked:
            option["reason"] = next_step["reason"]
        options.append(option)
    return options


def _experience_response(context: dict[str, Any], current_chamber: str) -> dict[str, Any]:
    project = context.get("project") or {}
    family = context.get("family") or {}
    entitlements = context.get("resolved_entitlements") or {}
    package_lane = _normalize(
        entitlements.get("package_lane") or project.get("project_lane") or "portrait"
    ).lower() or "portrait"
    family_id = _normalize(family.get("_id"))
    recommended_next = _recommended_next_step(context)
    presence = build_presence_overview(
        project_id=_normalize(project.get("_id")),
        family_id=family_id,
    )

    if family_id:
        lineage_summary = build_lineage_chamber_summary(family_id)
        story = build_experience_story(family_id)
        archive_progress = {
            "pending_uploads": lineage_summary["pending_uploads"],
            "narrative_ready_segments": lineage_summary["narrative_ready_segments"],
        }
        verification_progress = lineage_summary["trust_state"]
        featured_focus = _family_snapshot(context)
        urgent_tasks = [
            checkpoint["detail"]
            for checkpoint in _build_checkpoints(context)
            if not checkpoint["completed"]
        ][:3]
        suggested_storyline_moment = story["opening_summary"]
    else:
        archive_progress = {"pending_uploads": 0, "narrative_ready_segments": 0}
        verification_progress = {
            "member_count": 0,
            "relationship_count": 0,
            "verified_records": 0,
            "pending_records": 0,
            "contradictory_records": 0,
            "certificate_ready": False,
        }
        featured_focus = _family_snapshot(context)
        urgent_tasks = [recommended_next["reason"]]
        suggested_storyline_moment = "The chamber is waiting for its first anchored family branch."

    return {
        "project_id": _normalize(project.get("_id")),
        "family_id": family_id or None,
        "package_lane": package_lane,
        "current_chamber": current_chamber,
        "chamber_title": chamber_label(current_chamber),
        "allowed_transitions": _allowed_transition_options(context, current_chamber),
        "featured_focus": featured_focus,
        "urgent_tasks": urgent_tasks,
        "verification_progress": verification_progress,
        "archive_progress": archive_progress,
        "suggested_storyline_moment": suggested_storyline_moment,
        "live_event_count": presence["active_connections"],
        "recommended_next_transition": recommended_next["chamber"],
        "unlocked_modules": build_module_unlocks(
            package_lane,
            entitlements,
            is_admin=bool(context.get("is_admin")),
        ),
        "checkpoints": _build_checkpoints(context),
    }


def get_experience_session(current_user: dict[str, Any], *, project_id: str = "") -> dict[str, Any]:
    context = _resolve_context(current_user, project_id)
    user_id = _normalize(current_user.get("id") or current_user.get("_id") or current_user.get("user_id"))
    project = context.get("project") or {}
    project_id_value = _normalize(project.get("_id"))
    entitlements = context.get("resolved_entitlements") or {}
    package_lane = _normalize(
        entitlements.get("package_lane") or project.get("project_lane") or "portrait"
    ).lower() or "portrait"

    session_document = _load_session_document(user_id, project_id_value)
    current_chamber = _normalize((session_document or {}).get("current_chamber"))
    allowed_chambers = set(get_lane_chambers(package_lane))
    if current_chamber not in allowed_chambers:
        current_chamber = _default_chamber(package_lane, family_exists=bool(context.get("family")))

    return _experience_response(context, current_chamber)


def start_experience_session(
    current_user: dict[str, Any],
    payload: ExperienceSessionStartRequest,
) -> dict[str, Any]:
    context = _resolve_context(current_user, payload.project_id)
    user_id = _normalize(current_user.get("id") or current_user.get("_id") or current_user.get("user_id"))
    project = context.get("project") or {}
    project_id_value = _normalize(project.get("_id"))
    entitlements = context.get("resolved_entitlements") or {}
    package_lane = _normalize(
        entitlements.get("package_lane") or project.get("project_lane") or "portrait"
    ).lower() or "portrait"

    allowed_chambers = get_lane_chambers(package_lane)
    requested_chamber = _normalize(payload.preferred_chamber)
    if requested_chamber in allowed_chambers:
        current_chamber = requested_chamber
    else:
        current_chamber = _default_chamber(
            package_lane,
            family_exists=bool(context.get("family")),
        )

    now_iso = _now_iso()
    _experience_collection().update_one(
        {"user_id": user_id, "project_id": project_id_value},
        {
            "$set": {
                "current_chamber": current_chamber,
                "package_lane": package_lane,
                "updated_at": now_iso,
            },
            "$setOnInsert": {
                "created_at": now_iso,
            },
        },
        upsert=True,
    )
    return _experience_response(context, current_chamber)


def transition_experience_session(
    current_user: dict[str, Any],
    payload: ExperienceTransitionRequest,
) -> dict[str, Any]:
    context = _resolve_context(current_user, payload.project_id)
    user_id = _normalize(current_user.get("id") or current_user.get("_id") or current_user.get("user_id"))
    project = context.get("project") or {}
    project_id_value = _normalize(project.get("_id"))
    entitlements = context.get("resolved_entitlements") or {}
    package_lane = _normalize(
        entitlements.get("package_lane") or project.get("project_lane") or "portrait"
    ).lower() or "portrait"

    requested_chamber = _normalize(payload.next_chamber)
    if requested_chamber not in get_lane_chambers(package_lane):
        raise ValueError("Requested chamber is not available for this package lane.")

    now_iso = _now_iso()
    _experience_collection().update_one(
        {"user_id": user_id, "project_id": project_id_value},
        {
            "$set": {
                "current_chamber": requested_chamber,
                "package_lane": package_lane,
                "updated_at": now_iso,
            },
            "$setOnInsert": {
                "created_at": now_iso,
            },
        },
        upsert=True,
    )
    return _experience_response(context, requested_chamber)


def build_experience_map(current_user: dict[str, Any], *, project_id: str = "") -> dict[str, Any]:
    context = _resolve_context(current_user, project_id)
    project = context.get("project") or {}
    entitlements = context.get("resolved_entitlements") or {}
    package_lane = _normalize(
        entitlements.get("package_lane") or project.get("project_lane") or "portrait"
    ).lower() or "portrait"
    recommended_entry = _default_chamber(package_lane, family_exists=bool(context.get("family")))

    return {
        "project_id": _normalize(project.get("_id")),
        "package_lane": package_lane,
        "recommended_entry_chamber": recommended_entry,
        "chamber_sequence": get_lane_chambers(package_lane),
        "available_chambers": _allowed_transition_options(context, current_chamber=""),
    }


def list_experience_checkpoints(current_user: dict[str, Any], *, project_id: str = "") -> list[dict[str, Any]]:
    context = _resolve_context(current_user, project_id)
    return _build_checkpoints(context)


def get_recommended_next_step(current_user: dict[str, Any], *, project_id: str = "") -> dict[str, str]:
    context = _resolve_context(current_user, project_id)
    return _recommended_next_step(context)


def get_module_unlocks(current_user: dict[str, Any], *, project_id: str = "") -> list[dict[str, Any]]:
    context = _resolve_context(current_user, project_id)
    project = context.get("project") or {}
    entitlements = context.get("resolved_entitlements") or {}
    package_lane = _normalize(
        entitlements.get("package_lane") or project.get("project_lane") or "portrait"
    ).lower() or "portrait"
    return build_module_unlocks(
        package_lane,
        entitlements,
        is_admin=bool(context.get("is_admin")),
    )
