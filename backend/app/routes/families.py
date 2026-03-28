from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_database
from app.dependencies.auth import INTERNAL_ADMIN_KEYS, get_current_user
from app.schemas.family import FamilyCreate, FamilyResponse, build_family_response

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


def _is_admin(user: dict[str, Any]) -> bool:
    role = str(user.get("role", "")).strip().lower()
    access_tier = str(user.get("access_tier", "")).strip().lower()
    department_role = str(user.get("department_role", "")).strip().lower()

    return (
        role in INTERNAL_ADMIN_KEYS
        or access_tier in INTERNAL_ADMIN_KEYS
        or department_role in INTERNAL_ADMIN_KEYS
    )


def _family_is_visible_to_user(
    family: dict[str, Any],
    current_user_id: str,
    current_user_email: str,
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

    current_user_id = _current_user_id(user)
    current_user_email = _current_user_email(user)

    docs = list(families_collection.find().sort("created_at", -1))

    results: list[FamilyResponse] = []

    if _is_admin(user):
        for family in docs:
            built = _safe_build_family_response(family)
            if built is not None:
                results.append(built)
        return results

    for family in docs:
        if _family_is_visible_to_user(
            family=family,
            current_user_id=current_user_id,
            current_user_email=current_user_email,
        ):
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

    family_name = str(payload.family_name).strip()
    created_by = str(payload.created_by).strip() if payload.created_by else ""
    description = str(payload.description).strip() if payload.description else None

    if not family_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Family name is required.",
        )

    if not created_by:
        created_by = str(user.get("full_name") or current_user_email).strip()

    existing = families_collection.find_one(
        {
            "family_name": family_name,
            "owner_user_id": current_user_id,
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
        "owner_user_id": current_user_id,
        "owner_email": current_user_email,
        "visibility": "private",
        "shared_with_user_ids": [],
        "shared_with_emails": [],
        "created_at": datetime.now(UTC),
    }

    result = families_collection.insert_one(family_doc)
    family_doc["_id"] = result.inserted_id

    return build_family_response(family_doc)