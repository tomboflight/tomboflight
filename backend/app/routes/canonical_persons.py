from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.database import get_database
from app.dependencies.auth import get_current_user, require_admin
from app.schemas.canonical_person import (
    CanonicalPersonCreate,
    CanonicalPersonResponse,
    build_canonical_person_response,
)
from app.services.canonical_person_service import (
    create_canonical_person,
    list_canonical_persons,
)

router = APIRouter(prefix="/canonical-persons", tags=["Canonical Persons"])


def serialize_member(member: dict) -> dict:
    member["_id"] = str(member["_id"])
    return member


@router.get("/", response_model=list[CanonicalPersonResponse])
def get_canonical_persons(current_user: dict = Depends(get_current_user)):
    persons = list_canonical_persons()
    return [build_canonical_person_response(person) for person in persons]


@router.get("/{canonical_person_id}", response_model=CanonicalPersonResponse)
def get_canonical_person(
    canonical_person_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    if not ObjectId.is_valid(canonical_person_id):
        raise HTTPException(status_code=400, detail="Invalid canonical person id.")

    person = db.canonical_persons.find_one({"_id": ObjectId(canonical_person_id)})
    if not person:
        raise HTTPException(status_code=404, detail="Canonical person not found.")

    return build_canonical_person_response(person)


@router.get("/{canonical_person_id}/members")
def get_canonical_person_members(
    canonical_person_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    if not ObjectId.is_valid(canonical_person_id):
        raise HTTPException(status_code=400, detail="Invalid canonical person id.")

    canonical_person = db.canonical_persons.find_one({"_id": ObjectId(canonical_person_id)})
    if not canonical_person:
        raise HTTPException(status_code=404, detail="Canonical person not found.")

    identity_links = list(
        db.identity_links.find({"canonical_person_id": canonical_person_id})
    )

    member_ids = []
    for link in identity_links:
        family_member_id = link.get("family_member_id")
        if family_member_id and ObjectId.is_valid(family_member_id):
            member_ids.append(ObjectId(family_member_id))

    members = []
    if member_ids:
        members_cursor = db.family_members.find({"_id": {"$in": member_ids}})
        members = [serialize_member(member) for member in members_cursor]

    return {
        "canonical_person_id": canonical_person_id,
        "member_count": len(members),
        "members": members,
    }


@router.post("/", response_model=CanonicalPersonResponse)
def create_canonical_person_route(
    payload: CanonicalPersonCreate,
    current_user: dict = Depends(require_admin),
):
    person = create_canonical_person(payload)
    return build_canonical_person_response(person)