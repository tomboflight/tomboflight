from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.dependencies.auth import get_current_user, has_internal_admin_access
from app.services.lineage_query_service import LineageQueryService

router = APIRouter(prefix="/lineage-query", tags=["Lineage Query"])


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


def _require_family_access_by_family_id(
    family_id: str,
    db,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    if not family_id:
        raise HTTPException(status_code=400, detail="family_id is required.")

    if not ObjectId.is_valid(family_id):
        raise HTTPException(status_code=400, detail="Invalid family id.")

    family = db["families"].find_one({"_id": ObjectId(family_id)})
    if not family:
        raise HTTPException(status_code=404, detail="Family not found.")

    if _is_admin(current_user):
        return family

    current_user_id = _current_user_id(current_user)
    current_user_email = _current_user_email(current_user)
    current_user_name = _current_user_display_name(current_user)

    if not _family_is_visible_to_user(
        family=family,
        current_user_id=current_user_id,
        current_user_email=current_user_email,
        current_user_name=current_user_name,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this family.",
        )

    return family


def _require_member_access(
    member_id: str,
    db,
    current_user: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not ObjectId.is_valid(member_id):
        raise HTTPException(status_code=400, detail="Invalid member id.")

    member = db["family_members"].find_one({"_id": ObjectId(member_id)})
    if not member:
        raise HTTPException(status_code=404, detail="Family member not found.")

    family_id = str(member.get("family_id") or "").strip()
    family = _require_family_access_by_family_id(family_id, db, current_user)
    return member, family


@router.get("/ancestors/{member_id}")
async def get_ancestors(
    member_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = request.app.state.db
    service = LineageQueryService(db)

    _member, _family = _require_member_access(member_id, db, current_user)
    return service.get_ancestors(member_id)


@router.get("/descendants/{member_id}")
async def get_descendants(
    member_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = request.app.state.db
    service = LineageQueryService(db)

    _member, _family = _require_member_access(member_id, db, current_user)
    return service.get_descendants(member_id)


@router.get("/tree/{member_id}")
async def get_tree(
    member_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = request.app.state.db
    service = LineageQueryService(db)

    _member, _family = _require_member_access(member_id, db, current_user)
    return service.get_tree(member_id)


@router.get("/family-graph/{family_id}")
async def get_family_graph(
    family_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = request.app.state.db
    service = LineageQueryService(db)

    _require_family_access_by_family_id(family_id, db, current_user)
    return service.get_family_graph(family_id)


@router.get("/neighbors/{member_id}")
async def get_neighbors(
    member_id: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = request.app.state.db
    service = LineageQueryService(db)

    _member, _family = _require_member_access(member_id, db, current_user)
    return service.get_member_neighbors(member_id)
