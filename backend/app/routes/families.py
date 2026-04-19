from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_database
from app.dependencies.auth import (
    get_current_user,
    has_internal_admin_access,
    require_any_package_capability,
)
from app.schemas.family import FamilyCreate, FamilyResponse, build_family_response
from app.services.workspace_access_service import (
    list_accessible_families_for_user,
    require_workspace_capability,
    require_workspace_member_role,
)

router = APIRouter(prefix="/families", tags=["Families"])


def _current_user_id(user: dict[str, Any]) -> str:
    raw_id = user.get("id") or user.get("_id") or user.get("user_id")
    if raw_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing.",
        )
    return str(raw_id)


def _current_user_email(user: dict[str, Any]) -> str:
    raw_email = user.get("email")
    if not raw_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user email is missing.",
        )
    return str(raw_email).strip().lower()


def _current_user_display_name(user: dict[str, Any]) -> str:
    raw_name = user.get("full_name") or user.get("name") or ""
    return str(raw_name).strip()


def _is_admin(user: dict[str, Any]) -> bool:
    return has_internal_admin_access(user)


def _family_is_visible_to_user(
    family: dict[str, Any],
    current_user_id: str,
    current_user_email: str,
    current_user_name: str,
) -> bool:
    owner_user_id = str(family.get("owner_user_id") or "").strip()
    owner_email = str(family.get("owner_email") or "").strip().lower()

    shared_with_user_ids = [
        str(value).strip()
        for value in (family.get("shared_with_user_ids") or [])
        if value is not None
    ]
    shared_with_emails = [
        str(value).strip().lower()
        for value in (family.get("shared_with_emails") or [])
        if value is not None
    ]

    if owner_user_id and owner_user_id == current_user_id:
        return True

    if owner_email and owner_email == current_user_email:
        return True

    if current_user_id in shared_with_user_ids:
        return True

    if current_user_email in shared_with_emails:
        return True

    # Backward-compatible fallback for older family records
    if not owner_user_id and not owner_email:
        created_by = str(family.get("created_by") or "").strip()
        if created_by and (
            created_by == current_user_name or created_by.lower() == current_user_email
        ):
            return True

    return False


def _safe_build_family_response(family: dict[str, Any]) -> FamilyResponse | None:
    try:
        return build_family_response(family)
    except Exception:
        return None


@router.get("", response_model=list[FamilyResponse], include_in_schema=False)
@router.get("/", response_model=list[FamilyResponse])
def get_families(user: dict[str, Any] = Depends(get_current_user)):
    db = get_database()
    families_collection = db["families"]

    docs = list(families_collection.find().sort("created_at", -1))

    results: list[FamilyResponse] = []

    if has_internal_admin_access(user):
        for family in docs:
            built = _safe_build_family_response(family)
            if built is not None:
                results.append(built)
        return results

    for family in list_accessible_families_for_user(user):
        built = _safe_build_family_response(family)
        if built is not None:
            results.append(built)

    return results


@router.post(
    "",
    response_model=FamilyResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
@router.post("/", response_model=FamilyResponse, status_code=status.HTTP_201_CREATED)
def create_family_route(
    payload: FamilyCreate,
    user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    families_collection = db["families"]

    current_user_id = _current_user_id(user)
    current_user_email = _current_user_email(user)
    is_admin = has_internal_admin_access(user)

    family_name = str(payload.family_name).strip()
    created_by = str(payload.created_by).strip() if payload.created_by else ""
    description = str(payload.description).strip() if payload.description else None
    project_id = str(payload.project_id or "").strip()

    if not family_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Family name is required.",
        )

    if not created_by:
        created_by = str(user.get("full_name") or current_user_email).strip()

    project = None
    if is_admin:
        if project_id:
            context = require_workspace_capability(
                user,
                project_id=project_id,
                capabilities=("can_build_family_tree", "can_open_family_intake"),
                detail="This workspace does not support family build access.",
            )
            project = context["project"]
    else:
        if not project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="project_id is required to create a family inside a workspace.",
            )
        context = require_workspace_capability(
            user,
            project_id=project_id,
            capabilities=("can_build_family_tree", "can_open_family_intake"),
            detail="Your active package does not include family build access.",
        )
        require_workspace_member_role(
            context,
            allowed_roles=("billing_owner", "co_owner", "family_manager"),
            detail="Your role cannot create a new family workspace root.",
        )
        project = context["project"]

    if project is not None:
        existing_project_family_id = str(project.get("family_id") or "").strip()
        existing_project_family = (
            families_collection.find_one({"project_id": str(project.get("_id"))})
            if not existing_project_family_id
            else None
        )
        if existing_project_family_id or existing_project_family is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This workspace already has a family root. "
                    "Use the existing family workspace instead of creating a new root."
                ),
            )

    existing = families_collection.find_one(
        {
            "family_name": family_name,
            "owner_user_id": current_user_id if not is_admin else str(project.get("owner_user_id") or current_user_id) if project is not None else current_user_id,
        }
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A family with this name already exists for this account.",
        )

    family_doc = {
        "family_name": family_name,
        "created_by": created_by,
        "description": description,
        "project_id": str(project.get("_id")) if project is not None else None,
        "owner_user_id": str(project.get("owner_user_id") or current_user_id) if project is not None else current_user_id,
        "owner_email": str(project.get("owner_email") or current_user_email).strip().lower() if project is not None else current_user_email,
        "visibility": "private",
        "shared_with_user_ids": [],
        "shared_with_emails": [],
        "package_code": str(project.get("package_code") or "").strip() if project is not None else None,
        "package_name": str(project.get("package_name") or "").strip() if project is not None else None,
        "created_at": datetime.now(UTC),
    }

    result = families_collection.insert_one(family_doc)
    family_doc["_id"] = result.inserted_id

    if project is not None:
        db["projects"].update_one(
            {"_id": project["_id"]},
            {"$set": {"family_id": str(result.inserted_id), "updated_at": datetime.now(UTC)}},
        )

    return build_family_response(family_doc)
