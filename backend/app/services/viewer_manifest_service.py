from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.core.package_type_catalog import normalize_package_type
from app.core.state_catalog import normalize_visibility_state
from app.core.package_catalog import get_package
from app.database import get_database
from app.dependencies.auth import has_internal_admin_access
from app.services.project_service import list_projects

DEFAULT_EYE_TARGETS = {
    "left": {"x": 18, "y": 50},
    "right": {"x": 82, "y": 50},
}


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_value(value: Any) -> str:
    return str(value or "").strip()


def _normalize_email(value: Any) -> str:
    return _normalize_value(value).lower()


def _family_id_candidates(family_id: str) -> list[Any]:
    candidates: list[Any] = [family_id]
    if ObjectId.is_valid(family_id):
        candidates.append(ObjectId(family_id))
    return candidates


def _current_user_id(user: dict[str, Any]) -> str:
    return _normalize_value(user.get("id") or user.get("_id") or user.get("user_id"))


def _current_user_email(user: dict[str, Any]) -> str:
    return _normalize_email(user.get("email"))


def _display_name(member: dict[str, Any]) -> str:
    joined = f"{_normalize_value(member.get('first_name'))} {_normalize_value(member.get('last_name'))}".strip()
    return joined or _normalize_value(member.get("display_name")) or "Unknown Member"


def _split_name(full_name: str, fallback_email: str) -> tuple[str, str]:
    name = _normalize_value(full_name)
    if not name:
        local_part = (
            _normalize_email(fallback_email).split("@")[0].replace(".", " ").replace("_", " ")
        )
        name = local_part.strip()

    parts = [part for part in name.split() if part]
    if not parts:
        return "Primary", "Contact"
    if len(parts) == 1:
        return parts[0], "Contact"
    return parts[0], " ".join(parts[1:])


def _coerce_visibility(value: Any) -> str:
    return normalize_visibility_state(value)


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return _now()
    return _now()


def _sort_projects(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        projects,
        key=lambda item: _to_datetime(item.get("updated_at") or item.get("created_at")),
        reverse=True,
    )


def _sort_members(members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def _generation(member: dict[str, Any]) -> tuple[int, str]:
        raw_generation = member.get("generation")
        if isinstance(raw_generation, int):
            generation = raw_generation
        else:
            try:
                generation = int(raw_generation) # type: ignore
            except Exception:
                generation = 999
        return generation, _display_name(member).lower()

    return sorted(members, key=_generation)


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except Exception:
        return None


def _lane_from_project(project: dict[str, Any]) -> str:
    lane = normalize_package_type(project.get("project_lane"))
    if lane:
        return lane

    package = get_package(_normalize_value(project.get("package_code")))
    return normalize_package_type((package or {}).get("package_lane"), default="portrait")


def _find_submission_for_project(project: dict[str, Any]) -> dict[str, Any] | None:
    db = get_database()
    if db is None:
        return None

    submissions = db["intake_submissions"]
    intake_submission_id = _normalize_value(project.get("intake_submission_id"))
    project_id = _normalize_value(project.get("_id") or project.get("id"))
    owner_user_id = _normalize_value(project.get("owner_user_id"))

    if intake_submission_id and ObjectId.is_valid(intake_submission_id):
        found = submissions.find_one({"_id": ObjectId(intake_submission_id)})
        if found:
            return found

    if project_id:
        found = submissions.find_one({"project_id": project_id})
        if found:
            return found

    if owner_user_id and ObjectId.is_valid(owner_user_id):
        found = submissions.find_one(
            {"user_id": ObjectId(owner_user_id)},
            sort=[("created_at", -1)],
        )
        if found:
            return found

    return None


def resolve_project_for_viewer(
    *,
    current_user: dict[str, Any],
    project_id: str = "",
    family_id: str = "",
) -> dict[str, Any] | None:
    is_admin = has_internal_admin_access(current_user)
    normalized_project_id = _normalize_value(project_id)
    normalized_family_id = _normalize_value(family_id)

    if is_admin and not normalized_project_id and not normalized_family_id:
        return None

    projects = list_projects(
        owner_user_id=_current_user_id(current_user),
        owner_email=_current_user_email(current_user),
        is_admin=is_admin,
    )

    sorted_projects = _sort_projects(projects)

    if normalized_project_id:
        for project in sorted_projects:
            candidate_id = _normalize_value(project.get("_id") or project.get("id"))
            if candidate_id == normalized_project_id:
                return project
        return None

    if normalized_family_id:
        for project in sorted_projects:
            if _normalize_value(project.get("family_id")) == normalized_family_id:
                return project
        db = get_database()
        if db is not None and ObjectId.is_valid(normalized_family_id):
            family_doc = db["families"].find_one({"_id": ObjectId(normalized_family_id)})
            family_project_id = _normalize_value((family_doc or {}).get("project_id"))
            if family_project_id:
                for project in sorted_projects:
                    candidate_id = _normalize_value(project.get("_id") or project.get("id"))
                    if candidate_id == family_project_id:
                        return project
        return None

    return sorted_projects[0] if sorted_projects else None


def _build_anchor_family_name(
    *,
    lane: str,
    project: dict[str, Any],
    submission: dict[str, Any] | None,
) -> str:
    household = submission.get("household") if isinstance(submission, dict) else {}
    family_map = submission.get("family_map") if isinstance(submission, dict) else {}
    package_name = _normalize_value(project.get("package_name")) or "Tomb of Light"
    project_name = _normalize_value(project.get("project_name") or project.get("name"))
    owner_email = _normalize_email(project.get("owner_email"))
    owner_name = _normalize_value(
        household.get("primary_contact_name")
        if isinstance(household, dict)
        else ""
    ) or _normalize_value(project.get("owner_name"))

    if not owner_name and owner_email:
        owner_name = owner_email.split("@")[0].replace(".", " ").replace("_", " ").title()

    if lane in {"household", "network"}:
        return (
            _normalize_value(household.get("household_name")) # type: ignore
            or _normalize_value(family_map.get("family_branch_name")) # type: ignore
            or project_name
            or "Tomb of Light Family"
        )

    if lane == "organization":
        base = (
            _normalize_value(household.get("household_name")) # type: ignore
            or project_name
            or package_name
            or "Organization Workspace"
        )
        return f"{base} Command Workspace"

    base = owner_name or project_name or package_name or "Portrait Workspace"
    return f"{base} Portrait Workspace"


def _build_anchor_description(
    *,
    lane: str,
    project: dict[str, Any],
    submission: dict[str, Any] | None,
) -> str:
    household = submission.get("household") if isinstance(submission, dict) else {}
    family_map = submission.get("family_map") if isinstance(submission, dict) else {}
    review = submission.get("review") if isinstance(submission, dict) else {}

    return (
        _normalize_value(family_map.get("family_structure_summary")) # type: ignore
        or _normalize_value(household.get("project_scope")) # type: ignore
        or _normalize_value(review.get("final_intake_notes")) # type: ignore
        or _normalize_value(project.get("notes"))
        or (
            "Private lineage viewer workspace for guided family portraits."
            if lane in {"household", "network"}
            else "Private portrait viewer workspace for guided legacy delivery."
            if lane == "portrait"
            else "Private structure viewer workspace for guided organizational records."
        )
    )


def _serialize_family_summary(family: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _normalize_value(family.get("_id")),
        "family_name": _normalize_value(family.get("family_name")) or "Workspace",
        "description": _normalize_value(family.get("description")),
        "visibility": _normalize_value(family.get("visibility")) or "private",
    }


def _serialize_project_summary(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _normalize_value(project.get("_id") or project.get("id")),
        "name": _normalize_value(project.get("project_name") or project.get("name")) or "Workspace",
        "package_name": _normalize_value(project.get("package_name")) or "Tomb of Light Package",
        "package_code": _normalize_value(project.get("package_code")),
        "lane": _lane_from_project(project),
        "family_id": _normalize_value(project.get("family_id")) or None,
    }


def load_project_workspace_anchor(
    *,
    project: dict[str, Any],
    submission: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]:
    """Load the current workspace anchor state without creating missing records."""
    db = get_database()
    if db is None:
        return None, None, project

    submission = submission or _find_submission_for_project(project)
    families = db["families"]
    family_members = db["family_members"]

    project_id = _normalize_value(project.get("_id") or project.get("id"))
    owner_user_id = _normalize_value(project.get("owner_user_id"))
    owner_email = _normalize_email(project.get("owner_email"))
    submission_id = _normalize_value((submission or {}).get("_id"))

    family_doc = None
    existing_family_id = _normalize_value(project.get("family_id"))

    if existing_family_id and ObjectId.is_valid(existing_family_id):
        family_doc = families.find_one({"_id": ObjectId(existing_family_id)})

    if family_doc is None and submission_id:
        family_doc = families.find_one({"intake_submission_id": submission_id})

    if family_doc is None and project_id:
        family_doc = families.find_one({"project_id": project_id})

    family_id = _normalize_value((family_doc or {}).get("_id"))
    primary_member = None
    if family_id:
        member_query: dict[str, Any] = {
            "family_id": {"$in": _family_id_candidates(family_id)},
        }
        owned_member_filters: list[dict[str, Any]] = []
        if owner_user_id:
            owned_member_filters.append({"owner_user_id": owner_user_id})
        if owner_email:
            owned_member_filters.append({"owner_email": owner_email})

        if owned_member_filters:
            primary_member = family_members.find_one(
                {
                    "$and": [
                        member_query,
                        {"$or": owned_member_filters},
                    ]
                },
                sort=[("created_at", 1)],
            )

        if primary_member is None:
            primary_member = family_members.find_one(
                member_query,
                sort=[("created_at", 1)],
            )

    return family_doc, primary_member, project


def ensure_project_workspace_anchor(
    *,
    project: dict[str, Any],
    submission: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]:
    db = get_database()
    if db is None:
        return None, None, project

    lane = _lane_from_project(project)
    if lane not in {"portrait", "household", "network", "organization"}:
        return None, None, project

    submission = submission or _find_submission_for_project(project)

    families = db["families"]
    family_members = db["family_members"]
    projects = db["projects"]

    project_id = _normalize_value(project.get("_id") or project.get("id"))
    project_object_id = project.get("_id")
    owner_user_id = _normalize_value(project.get("owner_user_id"))
    owner_email = _normalize_email(project.get("owner_email"))
    package_code = _normalize_value(project.get("package_code"))
    package_name = _normalize_value(project.get("package_name")) or "Tomb of Light Package"
    submission_id = _normalize_value((submission or {}).get("_id"))

    family_doc, primary_member, project = load_project_workspace_anchor(
        project=project,
        submission=submission,
    )
    existing_family_id = _normalize_value(project.get("family_id"))

    if family_doc is None:
        household = submission.get("household") if isinstance(submission, dict) else {}
        created_by = _normalize_value(
            household.get("primary_contact_name") if isinstance(household, dict) else ""
        ) or owner_email or "Tomb of Light"

        family_payload = {
            "family_name": _build_anchor_family_name(
                lane=lane,
                project=project,
                submission=submission,
            ),
            "created_by": created_by,
            "description": _build_anchor_description(
                lane=lane,
                project=project,
                submission=submission,
            ),
            "owner_user_id": owner_user_id,
            "owner_email": owner_email,
            "visibility": _coerce_visibility(
                ((submission or {}).get("consent") or {}).get("visibility_preference")
                if isinstance(submission, dict)
                else "private"
            ),
            "shared_with_user_ids": [],
            "shared_with_emails": [],
            "package_code": package_code,
            "package_slug": package_code,
            "package_name": package_name,
            "project_id": project_id,
            "workspace_lane": lane,
            "workspace_kind": "customer_workspace_anchor",
            "source": "viewer_workspace_anchor",
            "intake_submission_id": submission_id or None,
            "created_at": _now(),
            "updated_at": _now(),
        }
        result = families.insert_one(family_payload)
        family_payload["_id"] = result.inserted_id
        family_doc = family_payload

    family_id = _normalize_value(family_doc.get("_id"))

    if project_id and family_id:
        family_project_id = _normalize_value(family_doc.get("project_id"))
        if family_project_id != project_id and ObjectId.is_valid(family_id):
            families.update_one(
                {"_id": ObjectId(family_id)},
                {
                    "$set": {
                        "project_id": project_id,
                        "updated_at": _now(),
                    }
                },
            )
            refreshed_family = families.find_one({"_id": ObjectId(family_id)})
            if refreshed_family is not None:
                family_doc = refreshed_family

    if family_id and existing_family_id != family_id and project_object_id is not None:
        projects.update_one(
            {"_id": project_object_id},
            {
                "$set": {
                    "family_id": family_id,
                    "updated_at": _now(),
                }
            },
        )
        refreshed = projects.find_one({"_id": project_object_id})
        if refreshed:
            project = refreshed
        else:
            project = dict(project)
            project["family_id"] = family_id

    if family_id and primary_member is None:
        household = submission.get("household") if isinstance(submission, dict) else {}
        primary_contact_name = _normalize_value(
            household.get("primary_contact_name") if isinstance(household, dict) else ""
        )
        first_name, last_name = _split_name(primary_contact_name, owner_email)

        member_payload = {
            "family_id": family_id,
            "first_name": first_name,
            "last_name": last_name,
            "generation": 1,
            "bio": _build_anchor_description(
                lane=lane,
                project=project,
                submission=submission,
            ),
            "owner_user_id": owner_user_id,
            "owner_email": owner_email,
            "workspace_lane": lane,
            "source": "viewer_workspace_anchor",
            "intake_submission_id": submission_id or None,
            "is_verified": False,
            "verification_status": "unverified",
            "created_at": _now(),
            "updated_at": _now(),
        }
        result = family_members.insert_one(member_payload)
        member_payload["_id"] = result.inserted_id
        primary_member = member_payload

    return family_doc, primary_member, project


def _build_empty_state(
    *,
    lane: str,
    family: dict[str, Any] | None,
    project: dict[str, Any],
) -> dict[str, Any]:
    workspace_name = (
        _normalize_value((family or {}).get("family_name"))
        or _normalize_value(project.get("project_name") or project.get("name"))
        or "Private Workspace"
    )

    if lane == "organization":
        status = "Awaiting Command Portraits"
        description = (
            "Upload your first leadership or organization portrait in Verification Uploads to activate this cinematic workspace."
        )
    elif lane in {"household", "network"}:
        status = "Awaiting Family Portraits"
        description = (
            "Upload portraits for yourself or your family members in Verification Uploads to populate this cinematic viewer automatically."
        )
    else:
        status = "Awaiting Portrait Upload"
        description = (
            "Upload your portrait in Verification Uploads to activate your private cinematic viewer automatically."
        )

    return {
        "id": "workspace-anchor",
        "image": "",
        "title": workspace_name,
        "status": status,
        "node": workspace_name,
        "description": description,
        "narration": description,
        "left_state_id": None,
        "right_state_id": None,
        "eye_targets": DEFAULT_EYE_TARGETS,
    }


def _member_status(
    *,
    lane: str,
    member: dict[str, Any],
    primary_member_id: str,
    anchor_generation: int | None,
) -> str:
    member_id = _normalize_value(member.get("_id"))
    if member_id == primary_member_id:
        if lane == "organization":
            return "Command Anchor"
        return "Anchor Portrait"

    if lane == "organization":
        return "Leadership Layer"

    raw_generation = member.get("generation")
    try:
        generation = int(raw_generation) # type: ignore
    except Exception:
        generation = None

    if anchor_generation is not None and generation is not None:
        if generation < anchor_generation:
            return "Earlier Generation"
        if generation > anchor_generation:
            return "Next Generation"

    return "Parallel Branch"


def _sequence_members_for_viewer(
    *,
    lane: str,
    members: list[dict[str, Any]],
    primary_member: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    members_with_photos = [
        member
        for member in _sort_members(members)
        if _normalize_value(member.get("photo_upload_id"))
    ]

    primary_member_id = _normalize_value((primary_member or {}).get("_id"))

    if primary_member_id:
        for index, member in enumerate(members_with_photos):
            if _normalize_value(member.get("_id")) == primary_member_id:
                members_with_photos.insert(0, members_with_photos.pop(index))
                break

    if lane == "portrait" and primary_member_id:
        primary_photo = [
            member
            for member in members_with_photos
            if _normalize_value(member.get("_id")) == primary_member_id
        ]
        if primary_photo:
            return primary_photo

    return members_with_photos


def _resolve_member_photo_upload(
    *,
    db: Any,
    member: dict[str, Any],
    project_id: str,
    family_id: str,
) -> dict[str, Any] | None:
    uploads = db["uploaded_files"]
    member_id = _normalize_value(member.get("_id"))
    candidate_upload_ids: list[str] = []

    primary_upload_id = _normalize_value(member.get("photo_upload_id"))
    if primary_upload_id:
        candidate_upload_ids.append(primary_upload_id)

    fallback_cursor = uploads.find(
        {
            "project_id": project_id,
            "family_id": family_id,
            "member_id": member_id,
            "category": "member_photo",
        }
    ).sort("created_at", -1)

    for upload in fallback_cursor:
        upload_id = _normalize_value(upload.get("_id"))
        if upload_id and upload_id not in candidate_upload_ids:
            candidate_upload_ids.append(upload_id)

    for upload_id in candidate_upload_ids:
        if not ObjectId.is_valid(upload_id):
            continue
        upload = uploads.find_one({"_id": ObjectId(upload_id)})
        if upload is None:
            continue
        if _normalize_value(upload.get("category")) != "member_photo":
            continue
        if _normalize_value(upload.get("project_id")) != project_id:
            continue
        if _normalize_value(upload.get("family_id")) != family_id:
            continue
        if _normalize_value(upload.get("member_id")) != member_id:
            continue
        if not _normalize_value(upload.get("relative_path")):
            continue
        return upload

    return None


def build_viewer_manifest(
    *,
    current_user: dict[str, Any],
    project_id: str = "",
    family_id: str = "",
) -> dict[str, Any]:
    db = get_database()
    if db is None:
        raise ValueError("Database is not connected.")

    project = resolve_project_for_viewer(
        current_user=current_user,
        project_id=project_id,
        family_id=family_id,
    )
    if project is None:
        raise ValueError("Viewer workspace could not be resolved for this account.")

    submission = _find_submission_for_project(project)
    family_doc, primary_member, project = load_project_workspace_anchor(
        project=project,
        submission=submission,
    )

    lane = _lane_from_project(project)
    family_id_value = _normalize_value((family_doc or {}).get("_id") or project.get("family_id"))
    members: list[dict[str, Any]] = []
    if family_id_value:
        members = list(
            db["family_members"].find(
                {"family_id": {"$in": _family_id_candidates(family_id_value)}},
            ),
        )

    ordered_members = _sequence_members_for_viewer(
        lane=lane,
        members=members,
        primary_member=primary_member,
    )

    primary_member_id = _normalize_value((primary_member or {}).get("_id"))
    anchor_generation = _coerce_int((primary_member or {}).get("generation"))

    states: list[dict[str, Any]] = []
    if ordered_members:
        project_id_value = _normalize_value(project.get("_id") or project.get("id"))
        valid_member_views: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for member in ordered_members:
            upload_record = _resolve_member_photo_upload(
                db=db,
                member=member,
                project_id=project_id_value,
                family_id=family_id_value,
            )
            if upload_record is not None:
                valid_member_views.append((member, upload_record))

        for index, (member, upload_record) in enumerate(valid_member_views):
            member_id = _normalize_value(member.get("_id"))
            upload_id = _normalize_value(upload_record.get("_id"))
            title = _display_name(member)
            status = _member_status(
                lane=lane,
                member=member,
                primary_member_id=primary_member_id,
                anchor_generation=anchor_generation,
            )
            description = (
                f"Cinematic portrait view for {title} inside your private {lane} workspace."
            )
            if lane == "organization":
                description = (
                    f"Cinematic command portrait view for {title} inside your protected organization workspace."
                )
            states.append(
                {
                    "id": f"member-{member_id}",
                    "member_id": member_id,
                    "image": f"/uploads/{upload_id}/download" if upload_id else "",
                    "title": title,
                    "status": status,
                    "node": title,
                    "description": description,
                    "narration": description,
                    "left_state_id": f"member-{_normalize_value(valid_member_views[index - 1][0].get('_id'))}" if index > 0 else None,
                    "right_state_id": f"member-{_normalize_value(valid_member_views[index + 1][0].get('_id'))}" if index + 1 < len(valid_member_views) else None,
                    "eye_targets": DEFAULT_EYE_TARGETS,
                }
            )

    if not states:
        states.append(
            _build_empty_state(
                lane=lane,
                family=family_doc,
                project=project,
            )
        )

    package_name = _normalize_value(project.get("package_name")) or "Tomb of Light Package"
    workspace_name = (
        _normalize_value((family_doc or {}).get("family_name"))
        or _normalize_value(project.get("project_name") or project.get("name"))
        or "Private Workspace"
    )

    if lane == "organization":
        hero_title = "Private Structure Viewer"
        hero_body = (
            "Move through the protected command portrait sequence attached to your organization workspace."
        )
        path_title = "Structure Flow"
        nav_labels = {"left": "Foundations", "right": "Next Role"}
    elif lane in {"household", "network"}:
        hero_title = "Private Family Viewer"
        hero_body = (
            "Move through the uploaded family portraits attached to your protected lineage workspace."
        )
        path_title = "Family Flow"
        nav_labels = {"left": "Origins", "right": "Forward Line"}
    else:
        hero_title = "Private Portrait Viewer"
        hero_body = (
            "Move through the portrait sequence attached to your protected legacy workspace."
        )
        path_title = "Portrait Flow"
        nav_labels = {"left": "Origins", "right": "Forward View"}

    path_items = [
        f"{state['title']} — {state['status']}"
        for state in states[:6]
    ]

    return {
        "mode": "dynamic",
        "navigation_mode": "sequence",
        "hero_kicker": package_name,
        "hero_title": hero_title,
        "hero_body": hero_body,
        "workspace_name": workspace_name,
        "instructions": (
            "Hold C to reveal the Iris Gate. Hover the left or right side of the gaze field to arm your line, then scroll in to enter. "
            "Scroll out to return. Use the zoom buttons below only when you want a closer look at the portrait. (Full viewer only)"
        ),
        "path_title": path_title,
        "path_items": path_items,
        "nav_labels": nav_labels,
        "states": states,
        "initial_state_id": states[0]["id"] if states else "",
        "branch_options_by_state": {},
        "project": _serialize_project_summary(project),
        "family": _serialize_family_summary(family_doc) if family_doc else None,
        "primary_member_id": primary_member_id or None,
        "has_uploaded_portraits": any(_normalize_value(state.get("image")) for state in states),
    }
