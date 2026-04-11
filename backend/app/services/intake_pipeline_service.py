from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from app.core.package_catalog import get_package, normalize_package_code
from app.core.package_type_catalog import normalize_package_type
from app.core.state_catalog import normalize_visibility_state
from app.database import get_database
from app.dependencies.auth import transition_project
from app.services.viewer_manifest_service import ensure_project_workspace_anchor


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _oid(value: str) -> ObjectId:
    return ObjectId(value)


def _serialize_submission(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    out["id"] = str(out.pop("_id"))
    if "user_id" in out and isinstance(out["user_id"], ObjectId):
        out["user_id"] = str(out["user_id"])
    return out


def _normalize_visibility(value: str | None) -> str:
    return normalize_visibility_state(value)


def _normalize_package_code(value: str | None) -> str:
    normalized = normalize_package_code(value)
    return normalized or "unknown"


def _supports_family_build(package: dict[str, Any]) -> bool:
    return bool(
        package.get("can_build_family_tree") or package.get("can_build_household")
    )


def _supports_org_build(package: dict[str, Any]) -> bool:
    return bool(package.get("can_build_org_chart"))


def _split_name(full_name: str, fallback_email: str) -> tuple[str, str]:
    name = str(full_name or "").strip()
    if not name:
        local_part = (
            str(fallback_email or "")
            .split("@")[0]
            .replace(".", " ")
            .replace("_", " ")
        )
        name = local_part.strip()

    parts = [part for part in name.split() if part]
    if not parts:
        return "Primary", "Contact"
    if len(parts) == 1:
        return parts[0], "Contact"
    return parts[0], " ".join(parts[1:])


def _seed_primary_member(
    *,
    db,
    family_id: str,
    submission_id: str,
    owner_user_id: str,
    owner_email: str,
    household: dict[str, Any],
):
    family_members = db["family_members"]

    existing = family_members.find_one({"family_id": family_id})
    if existing is not None:
        return

    primary_contact_name = str(household.get("primary_contact_name") or "").strip()
    first_name, last_name = _split_name(primary_contact_name, owner_email)
    project_scope = str(household.get("project_scope") or "").strip()

    member_payload = {
        "family_id": family_id,
        "first_name": first_name,
        "last_name": last_name,
        "generation": 1,
        "bio": project_scope or "",
        "owner_user_id": owner_user_id,
        "owner_email": owner_email,
        "source": "approved_intake_seed",
        "intake_submission_id": submission_id,
        "is_verified": False,
        "verification_status": "unverified",
        "created_at": _now(),
        "updated_at": _now(),
    }

    family_members.insert_one(member_payload)


def provision_build_from_submission(
    *,
    submission_id: str,
    provisioned_by: str,
    provisioned_by_user_id: str,
    family_name_override: str = "",
    project_name_override: str = "",
    production_notes: str = "",
) -> dict[str, Any]:
    db = get_database()

    submissions = db["intake_submissions"]
    families = db["families"]
    households = db["households"]
    projects = db["projects"]

    submission = submissions.find_one({"_id": _oid(submission_id)})
    if not submission:
        raise ValueError("Intake submission not found.")

    status = str(submission.get("status", "")).strip().lower()
    allowed_statuses = {
        "approved",
        "build_ready",
        "in_production",
        "qa_review",
        "client_review",
        "delivered",
        "archived",
    }
    if status not in allowed_statuses:
        raise ValueError("Submission must be approved before provisioning a build.")

    existing_family_root_id = str(submission.get("family_root_id") or "").strip()
    existing_household_id = str(submission.get("household_id") or "").strip()
    existing_project_id = str(submission.get("project_id") or "").strip()

    household = submission.get("household") or {}
    family_map = submission.get("family_map") or {}
    consent = submission.get("consent") or {}
    review = submission.get("review") or {}

    owner_user_id = submission.get("user_id")
    owner_user_id_str = str(owner_user_id) if owner_user_id is not None else ""
    owner_email = str(submission.get("email") or "").strip().lower()

    package_code = _normalize_package_code(
        submission.get("package_code") or submission.get("package_slug")
    )
    package_name = (
        str(submission.get("package_name") or "").strip() or "Tomb of Light Package"
    )
    package = get_package(package_code) or {}
    project_lane = normalize_package_type(package.get("package_lane"), default="portrait")

    supports_family_build = _supports_family_build(package)
    supports_org_build = _supports_org_build(package)

    family_name = (
        family_name_override.strip()
        or str(household.get("household_name") or "").strip()
        or str(family_map.get("family_branch_name") or "").strip()
        or "Tomb of Light Family"
    )

    created_by = (
        str(household.get("primary_contact_name") or "").strip()
        or owner_email
        or "Unknown"
    )

    family_description = (
        str(family_map.get("family_structure_summary") or "").strip()
        or str(household.get("project_scope") or "").strip()
        or str(review.get("final_intake_notes") or "").strip()
        or None
    )

    visibility = _normalize_visibility(consent.get("visibility_preference"))

    family_root_id = ""
    household_id = ""

    if supports_family_build:
        family_doc = None
        if existing_family_root_id and ObjectId.is_valid(existing_family_root_id):
            family_doc = families.find_one({"_id": ObjectId(existing_family_root_id)})

        if family_doc is None:
            family_doc = families.find_one({"intake_submission_id": submission_id})

        if family_doc is None:
            family_payload = {
                "family_name": family_name,
                "created_by": created_by,
                "description": family_description,
                "owner_user_id": owner_user_id_str,
                "owner_email": owner_email,
                "visibility": visibility,
                "shared_with_user_ids": [],
                "shared_with_emails": [],
                "package_code": package_code,
                "package_slug": package_code,
                "package_name": package_name,
                "source": "approved_intake",
                "intake_submission_id": submission_id,
                "created_at": _now(),
                "updated_at": _now(),
            }
            family_result = families.insert_one(family_payload)
            family_payload["_id"] = family_result.inserted_id
            family_doc = family_payload

        family_root_id = str(family_doc["_id"])

        household_doc = None
        if existing_household_id and ObjectId.is_valid(existing_household_id):
            household_doc = households.find_one({"_id": ObjectId(existing_household_id)})

        if household_doc is None:
            household_doc = households.find_one({"intake_submission_id": submission_id})

        if household_doc is None:
            household_payload = {
                "family_id": family_root_id,
                "intake_submission_id": submission_id,
                "owner_user_id": owner_user_id_str,
                "owner_email": owner_email,
                "household_name": household.get("household_name"),
                "primary_contact_name": household.get("primary_contact_name"),
                "primary_contact_email": household.get("primary_contact_email"),
                "primary_contact_phone": household.get("primary_contact_phone"),
                "co_owner_name": household.get("co_owner_name"),
                "household_role": household.get("household_role"),
                "project_scope": household.get("project_scope"),
                "special_notes": household.get("special_notes"),
                "status": "build_ready",
                "source": "approved_intake",
                "created_at": _now(),
                "updated_at": _now(),
            }
            household_result = households.insert_one(household_payload)
            household_payload["_id"] = household_result.inserted_id
            household_doc = household_payload

        household_id = str(household_doc["_id"])

        _seed_primary_member(
            db=db,
            family_id=family_root_id,
            submission_id=submission_id,
            owner_user_id=owner_user_id_str,
            owner_email=owner_email,
            household=household,
        )

    project_doc = None
    if existing_project_id and ObjectId.is_valid(existing_project_id):
        project_doc = projects.find_one({"_id": ObjectId(existing_project_id)})

    if project_doc is None:
        project_doc = projects.find_one({"intake_submission_id": submission_id})

    if supports_family_build:
        default_project_name = f"{family_name} Production Build"
    elif supports_org_build:
        default_project_name = f"{package_name} Organization Workspace"
    else:
        default_project_name = f"{package_name} Portrait Workspace"

    project_name = project_name_override.strip() or default_project_name

    project_payload = {
        "name": project_name,
        "project_name": project_name,
        "project_lane": project_lane,
        "family_id": family_root_id or None,
        "household_id": household_id or None,
        "organization_id": None,
        "owner_user_id": owner_user_id_str,
        "owner_email": owner_email,
        "package_code": package_code,
        "package_slug": package_code,
        "package_type": package_code,
        "package_name": package_name,
        "item_type": "package",
        "billing_plan": "one_time",
        "source": "approved_intake",
        "intake_submission_id": submission_id,
        "created_by": provisioned_by,
        "notes": production_notes or "",
        "updated_at": _now(),
    }

    if project_doc is None:
        project_payload["status"] = "draft"
        project_payload["phase"] = "created"
        project_payload["created_at"] = _now()
        project_result = projects.insert_one(project_payload)
        project_payload["_id"] = project_result.inserted_id
        project_doc = project_payload
    else:
        projects.update_one(
            {"_id": project_doc["_id"]},
            {"$set": project_payload},
        )
        project_doc = projects.find_one({"_id": project_doc["_id"]}) or project_doc

    _family_doc, _primary_member, project_doc = ensure_project_workspace_anchor(
        project=project_doc,
        submission=submission,
    )

    project_id = str(project_doc["_id"])
    project_doc = transition_project(
        project_id,
        "build_ready",
        {"id": provisioned_by_user_id, "email": provisioned_by},
    )

    resolved_family_id = str(project_doc.get("family_id") or family_root_id or "").strip()
    if resolved_family_id and ObjectId.is_valid(resolved_family_id):
        families.update_one(
            {"_id": ObjectId(resolved_family_id)},
            {
                "$set": {
                    "project_id": project_id,
                    "updated_at": _now(),
                }
            },
        )

    submission_set: dict[str, Any] = {
        "status": "build_ready",
        "review_locked": True,
        "project_id": project_id,
        "project_lane": project_lane,
        "package_code": package_code,
        "package_slug": package_code,
        "package_name": package_name,
        "provisioned_at": _now(),
        "provisioned_by": provisioned_by,
        "production_notes": production_notes or "",
        "updated_at": _now(),
    }

    update_doc: dict[str, Any] = {"$set": submission_set}

    if supports_family_build:
        submission_set["family_root_id"] = family_root_id
        submission_set["household_id"] = household_id
    else:
        update_doc["$unset"] = {
            "family_root_id": "",
            "household_id": "",
        }

    submissions.update_one({"_id": _oid(submission_id)}, update_doc)

    saved = submissions.find_one({"_id": _oid(submission_id)})
    if not saved:
        raise RuntimeError("Failed to fetch provisioned intake submission.")

    return _serialize_submission(saved)
