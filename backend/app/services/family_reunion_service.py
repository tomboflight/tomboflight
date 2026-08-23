from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.database import get_database
from app.services.linked_network_service import build_linked_network


def _value(value: Any) -> str:
    return str(value or "").strip()


def _id_candidates(value: str) -> list[Any]:
    values: list[Any] = [value]
    if ObjectId.is_valid(value):
        values.append(ObjectId(value))
    return values


def _member_name(member: dict[str, Any]) -> str:
    return (
        _value(member.get("display_name"))
        or f"{_value(member.get('first_name'))} {_value(member.get('last_name'))}".strip()
        or "Unnamed family member"
    )


def _portrait_status(uploads: list[dict[str, Any]]) -> tuple[str, str | None]:
    if not uploads:
        return "missing", None
    ordered = sorted(
        uploads,
        key=lambda item: _value(item.get("created_at")),
        reverse=True,
    )
    for upload in ordered:
        if (
            _value(upload.get("scan_status")).lower() == "clean"
            and not bool(upload.get("quarantined"))
            and bool(upload.get("approved_for_cinematic"))
            and _value(upload.get("verification_status")).lower() == "approved"
            and _value(upload.get("consent_status")).lower() == "approved"
            and bool(upload.get("consent_attested"))
            and bool(upload.get("authority_attested"))
        ):
            return "approved", _value(upload.get("_id")) or None

    latest = ordered[0]
    if bool(latest.get("quarantined")) or _value(latest.get("scan_status")).lower() in {
        "infected",
        "error",
    }:
        return "security_blocked", None
    if _value(latest.get("scan_status")).lower() != "clean":
        return "pending_scan", None
    if _value(latest.get("verification_status")).lower() == "rejected":
        return "rejected", None
    if not (
        bool(latest.get("consent_attested"))
        and bool(latest.get("authority_attested"))
    ):
        return "consent_missing", None
    return "pending_master_review", None


def _verification_status(member: dict[str, Any], uploads: list[dict[str, Any]]) -> str:
    if bool(member.get("is_verified")) or _value(member.get("verification_status")).lower() == "verified":
        return "verified"
    if any(
        _value(upload.get("scan_status")).lower() == "clean"
        and not bool(upload.get("quarantined"))
        and _value(upload.get("verification_status")).lower() == "approved"
        for upload in uploads
    ):
        return "verified"
    if uploads:
        return "pending"
    return "not_submitted"


def _single_household_network(
    project_id: str,
    workspace_context: dict[str, Any],
) -> dict[str, Any]:
    db = get_database()
    project = workspace_context.get("project") or {}
    family = workspace_context.get("family") or {}
    family_id = _value(family.get("_id") or project.get("family_id"))
    household_id = _value(project.get("household_id") or family.get("household_id"))
    household = None
    if household_id:
        household = db["households"].find_one(
            {"_id": ObjectId(household_id) if ObjectId.is_valid(household_id) else household_id}
        )
    members = (
        list(db["family_members"].find({"family_id": {"$in": _id_candidates(family_id)}}))
        if family_id
        else []
    )
    return {
        "network_summary": {
            "root_project_id": project_id,
            "total_households": 1,
            "total_members": len(members),
            "alignment_conflict_count": 0,
            "unplaced_household_count": 0,
        },
        "households": [
            {
                "household_id": household_id,
                "household_name": _value((household or {}).get("household_name"))
                or _value(family.get("family_name"))
                or "Primary Household",
                "project_id": project_id,
                "family_id": family_id,
                "member_count": len(members),
                "is_own_household": True,
                "generation_offset": 0,
                "alignment_status": "aligned",
            }
        ],
        "nodes": [
            {
                "id": _value(member.get("_id")),
                "source_project_id": project_id,
                "source_household_id": household_id,
            }
            for member in members
        ],
        "edges": [],
        "alignment_conflicts": [],
    }


def build_family_reunion_readiness(
    project_id: str,
    current_user_id: str,
    *,
    workspace_context: dict[str, Any],
) -> dict[str, Any]:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")

    entitlements = workspace_context.get("resolved_entitlements") or {}
    if bool(entitlements.get("can_link_households")):
        network = build_linked_network(
            project_id,
            current_user_id,
            workspace_context=workspace_context,
        )
    else:
        network = _single_household_network(project_id, workspace_context)

    visible_nodes = {
        _value(node.get("id")): node
        for node in network.get("nodes") or []
        if _value(node.get("id"))
    }
    member_rows: list[dict[str, Any]] = []

    for member_id, node in visible_nodes.items():
        if not ObjectId.is_valid(member_id):
            continue
        member = db["family_members"].find_one({"_id": ObjectId(member_id)})
        if not member:
            continue
        project_id_for_member = _value(node.get("source_project_id")) or project_id
        photos = list(
            db["uploaded_files"].find(
                {
                    "project_id": project_id_for_member,
                    "member_id": member_id,
                    "category": "member_photo",
                }
            )
        )
        evidence = list(
            db["uploaded_files"].find(
                {
                    "project_id": project_id_for_member,
                    "member_id": member_id,
                    "category": "verification_evidence",
                }
            )
        )
        portrait_status, approved_photo_upload_id = _portrait_status(photos)
        verification_status = _verification_status(member, evidence)
        placement_status = _value(member.get("placement_status")) or "unplaced"

        account_required = bool(
            member.get("account_required")
            or member.get("invite_email")
            or member.get("account_email")
        )
        account_claimed = bool(
            member.get("account_user_id")
            or member.get("claimed_by_user_id")
            or member.get("user_id")
        )
        invite_email = _value(member.get("invite_email")).lower()
        if not account_claimed and invite_email:
            project_member = db["project_members"].find_one(
                {
                    "project_id": {"$in": _id_candidates(project_id_for_member)},
                    "$or": [
                        {"user_email": invite_email},
                        {"email": invite_email},
                    ],
                    "status": {"$nin": ["suspended", "revoked"]},
                }
            )
            account_claimed = bool(
                project_member
                and (
                    project_member.get("user_id")
                    or _value(project_member.get("status")).lower() == "active"
                )
            )
        if account_claimed:
            account_status = "claimed"
        elif account_required:
            account_status = "not_claimed"
        else:
            account_status = "not_required"

        verification_required = bool(member.get("verification_required"))
        incomplete_reasons: list[str] = []
        if portrait_status != "approved":
            incomplete_reasons.append(f"portrait_{portrait_status}")
        if placement_status not in {"placed", "root"}:
            incomplete_reasons.append("tree_placement_incomplete")
        if account_required and not account_claimed:
            incomplete_reasons.append("account_not_claimed")
        if verification_required and verification_status != "verified":
            incomplete_reasons.append("verification_incomplete")

        member_rows.append(
            {
                "member_id": member_id,
                "display_name": _member_name(member),
                "household_id": _value(node.get("source_household_id")),
                "project_id": project_id_for_member,
                "generation": member.get("generation"),
                "placement_status": placement_status,
                "portrait_status": portrait_status,
                "approved_photo_upload_id": approved_photo_upload_id,
                "verification_status": verification_status,
                "account_status": account_status,
                "account_required": account_required,
                "slide_ready": (
                    portrait_status == "approved"
                    and placement_status in {"placed", "root"}
                ),
                "complete": not incomplete_reasons,
                "incomplete_reasons": incomplete_reasons,
            }
        )

    household_rows: list[dict[str, Any]] = []
    for household in network.get("households") or []:
        household_id = _value(household.get("household_id"))
        members = [
            member for member in member_rows if member["household_id"] == household_id
        ]
        completed = sum(1 for member in members if member["complete"])
        household_rows.append(
            {
                **household,
                "completion": {
                    "complete_members": completed,
                    "total_members": len(members),
                    "percent": round((completed / len(members)) * 100)
                    if members
                    else 0,
                },
                "members": members,
            }
        )

    complete_members = sum(1 for member in member_rows if member["complete"])
    return {
        "project_id": project_id,
        "ready": bool(member_rows)
        and complete_members == len(member_rows)
        and not (network.get("alignment_conflicts") or []),
        "summary": {
            "household_count": len(household_rows),
            "member_count": len(member_rows),
            "complete_member_count": complete_members,
            "incomplete_member_count": len(member_rows) - complete_members,
            "slide_ready_count": sum(1 for member in member_rows if member["slide_ready"]),
            "alignment_conflict_count": len(network.get("alignment_conflicts") or []),
        },
        "households": household_rows,
        "alignment_conflicts": network.get("alignment_conflicts") or [],
        "privacy_boundary": (
            "This view contains completion states only. Private files, passwords, "
            "wallet secrets, and unshared living-person records are not exposed."
        ),
    }
