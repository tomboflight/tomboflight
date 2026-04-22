from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pymongo import ASCENDING
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from app.core.package_catalog import COMMAND_STRUCTURE_ORG_NODE_LIMIT
from app.database import get_database

TRANSITION_EVENT_TYPES = {
    "assumed_office",
    "assumed_command",
    "installed",
    "elected",
    "appointed",
    "promoted",
    "transferred",
    "retired",
    "resigned",
    "removed",
    "deceased",
    "emeritus_designation",
    "term_ended",
    "office_renamed",
    "unit_redesignated",
    "department_reorganized",
    "jurisdiction_changed",
    "district_changed",
    "charter_updated",
    "custom",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _collection(name: str) -> Collection[dict[str, Any]]:
    db = get_database()
    return db[name]


def ensure_organization_indexes() -> None:
    _collection("organization_profiles").create_index(
        [("organization_id", ASCENDING)],
        unique=True,
        name="organization_profile_id_uniq",
    )
    _collection("organization_nodes").create_index(
        [("organization_id", ASCENDING), ("node_key", ASCENDING)],
        unique=True,
        name="organization_node_natural_key_uniq",
    )
    _collection("organization_role_seats").create_index(
        [("organization_id", ASCENDING), ("node_id", ASCENDING), ("role_key", ASCENDING)],
        unique=True,
        name="organization_role_seat_natural_key_uniq",
    )
    _collection("organization_people").create_index(
        [("organization_id", ASCENDING), ("person_id", ASCENDING)],
        unique=True,
        name="organization_person_natural_key_uniq",
    )
    _collection("organization_assignments").create_index(
        [("organization_id", ASCENDING), ("assignment_id", ASCENDING)],
        unique=True,
        name="organization_assignment_id_uniq",
    )
    _collection("organization_support_records").create_index(
        [("organization_id", ASCENDING), ("support_record_id", ASCENDING)],
        unique=True,
        name="organization_support_record_id_uniq",
    )
    _collection("organization_links").create_index(
        [
            ("organization_id", ASCENDING),
            ("linked_organization_id", ASCENDING),
            ("link_type", ASCENDING),
        ],
        unique=True,
        name="organization_link_natural_key_uniq",
    )


def upsert_organization_profile(payload: dict[str, Any], *, actor_user_id: str) -> dict[str, Any]:
    collection = _collection("organization_profiles")
    doc = dict(payload)
    now = _utcnow()
    doc["updated_at"] = now
    doc["updated_by"] = actor_user_id
    existing = collection.find_one({"organization_id": doc["organization_id"]})
    if existing:
        doc["created_at"] = existing.get("created_at")
        doc["created_by"] = existing.get("created_by")
        collection.update_one({"_id": existing["_id"]}, {"$set": doc})
    else:
        doc["created_at"] = now
        doc["created_by"] = actor_user_id
        collection.insert_one(doc)
    return collection.find_one({"organization_id": doc["organization_id"]}) or {}


def list_organization_profiles(organization_id: str | None = None) -> list[dict[str, Any]]:
    query = {"organization_id": organization_id} if organization_id else {}
    return list(_collection("organization_profiles").find(query))


def create_organization_node(organization_id: str, payload: dict[str, Any], *, actor_user_id: str) -> dict[str, Any]:
    collection = _collection("organization_nodes")
    count = collection.count_documents({"organization_id": organization_id})
    if count >= COMMAND_STRUCTURE_ORG_NODE_LIMIT:
        raise ValueError(f"Organization node cap ({COMMAND_STRUCTURE_ORG_NODE_LIMIT}) reached.")

    doc = {
        "organization_id": organization_id,
        **payload,
        "created_at": _utcnow(),
        "created_by": actor_user_id,
    }
    try:
        collection.insert_one(doc)
    except DuplicateKeyError as exc:
        raise ValueError("Duplicate organization node for organization_id + node_key.") from exc
    return collection.find_one({"organization_id": organization_id, "node_key": payload["node_key"]}) or {}


def list_organization_nodes(organization_id: str) -> list[dict[str, Any]]:
    return list(_collection("organization_nodes").find({"organization_id": organization_id}))


def create_role_seat(organization_id: str, payload: dict[str, Any], *, actor_user_id: str) -> dict[str, Any]:
    collection = _collection("organization_role_seats")
    doc = {
        "organization_id": organization_id,
        **payload,
        "created_at": _utcnow(),
        "created_by": actor_user_id,
    }
    try:
        collection.insert_one(doc)
    except DuplicateKeyError as exc:
        raise ValueError("Duplicate role seat for organization_id + node_id + role_key.") from exc
    return collection.find_one(
        {
            "organization_id": organization_id,
            "node_id": payload["node_id"],
            "role_key": payload["role_key"],
        }
    ) or {}


def list_role_seats(organization_id: str) -> list[dict[str, Any]]:
    return list(_collection("organization_role_seats").find({"organization_id": organization_id}))


def create_person(organization_id: str, payload: dict[str, Any], *, actor_user_id: str) -> dict[str, Any]:
    collection = _collection("organization_people")
    doc = {"organization_id": organization_id, **payload, "created_at": _utcnow(), "created_by": actor_user_id}
    try:
        collection.insert_one(doc)
    except DuplicateKeyError as exc:
        raise ValueError("Duplicate person for organization_id + person_id.") from exc
    return collection.find_one({"organization_id": organization_id, "person_id": payload["person_id"]}) or {}


def list_people(organization_id: str) -> list[dict[str, Any]]:
    return list(_collection("organization_people").find({"organization_id": organization_id}))


def _find_current_assignment_for_role(organization_id: str, role_seat_id: str) -> dict[str, Any] | None:
    return _collection("organization_assignments").find_one(
        {
            "organization_id": organization_id,
            "role_seat_id": role_seat_id,
            "status": {"$in": ["active", "current", "interim", "acting"]},
            "end_date": None,
        }
    )


def create_assignment(organization_id: str, payload: dict[str, Any], *, actor_user_id: str) -> dict[str, Any]:
    assignments = _collection("organization_assignments")
    current = _find_current_assignment_for_role(organization_id, payload["role_seat_id"])
    if current and not payload.get("acting_or_interim"):
        raise ValueError("Duplicate current assignment is blocked unless acting/interim is selected.")

    doc = {
        "organization_id": organization_id,
        **payload,
        "created_at": _utcnow(),
        "created_by": actor_user_id,
        "updated_by": actor_user_id,
    }
    try:
        assignments.insert_one(doc)
    except DuplicateKeyError as exc:
        raise ValueError("Duplicate assignment_id for organization.") from exc
    return assignments.find_one({"organization_id": organization_id, "assignment_id": payload["assignment_id"]}) or {}


def end_assignment(
    organization_id: str,
    assignment_id: str,
    *,
    end_date: Any,
    status: str,
    notes: str | None,
    actor_user_id: str,
) -> dict[str, Any]:
    assignments = _collection("organization_assignments")
    existing = assignments.find_one({"organization_id": organization_id, "assignment_id": assignment_id})
    if not existing:
        raise ValueError("Assignment not found.")
    assignments.update_one(
        {"_id": existing["_id"]},
        {
            "$set": {
                "end_date": end_date,
                "status": status,
                "notes": notes or existing.get("notes"),
                "updated_by": actor_user_id,
                "updated_at": _utcnow(),
            }
        },
    )
    return assignments.find_one({"_id": existing["_id"]}) or {}


def replace_role_seat_assignment(
    organization_id: str,
    role_seat_id: str,
    payload: dict[str, Any],
    *,
    actor_user_id: str,
) -> dict[str, Any]:
    current = _find_current_assignment_for_role(organization_id, role_seat_id)
    if current:
        _collection("organization_assignments").update_one(
            {"_id": current["_id"]},
            {
                "$set": {
                    "status": "ended",
                    "end_date": payload["start_date"],
                    "updated_by": actor_user_id,
                    "updated_at": _utcnow(),
                }
            },
        )

    created = create_assignment(
        organization_id,
        {
            **payload,
            "role_seat_id": role_seat_id,
            "status": "active",
            "end_date": None,
        },
        actor_user_id=actor_user_id,
    )
    return {"replaced_assignment": current, "new_assignment": created}


def list_assignments(organization_id: str) -> list[dict[str, Any]]:
    return list(_collection("organization_assignments").find({"organization_id": organization_id}))


def create_transition(organization_id: str, payload: dict[str, Any], *, actor_user_id: str) -> dict[str, Any]:
    if payload.get("event_type") not in TRANSITION_EVENT_TYPES:
        raise ValueError("Unsupported transition event_type.")

    collection = _collection("organization_transitions")
    doc = {"organization_id": organization_id, **payload, "created_at": _utcnow(), "created_by": actor_user_id}
    collection.insert_one(doc)
    return collection.find_one({"organization_id": organization_id, "transition_id": payload["transition_id"]}) or {}


def list_transitions(organization_id: str) -> list[dict[str, Any]]:
    return list(_collection("organization_transitions").find({"organization_id": organization_id}))


def create_support_record(organization_id: str, payload: dict[str, Any], *, actor_user_id: str) -> dict[str, Any]:
    collection = _collection("organization_support_records")
    if collection.count_documents({"organization_id": organization_id}) >= 25:
        raise ValueError("Support upload cap (25) reached for organization.")
    doc = {"organization_id": organization_id, **payload, "created_at": _utcnow(), "created_by": actor_user_id}
    collection.insert_one(doc)
    return collection.find_one({"organization_id": organization_id, "support_record_id": payload["support_record_id"]}) or {}


def list_support_records(organization_id: str) -> list[dict[str, Any]]:
    return list(_collection("organization_support_records").find({"organization_id": organization_id}))


def create_linked_organization(organization_id: str, payload: dict[str, Any], *, actor_user_id: str) -> dict[str, Any]:
    collection = _collection("organization_links")
    doc = {"organization_id": organization_id, **payload, "created_at": _utcnow(), "created_by": actor_user_id}
    try:
        collection.insert_one(doc)
    except DuplicateKeyError as exc:
        raise ValueError("Duplicate organization link for organization_id + linked_organization_id + link_type.") from exc
    return collection.find_one(
        {
            "organization_id": organization_id,
            "linked_organization_id": payload["linked_organization_id"],
            "link_type": payload["link_type"],
        }
    ) or {}


def list_links(organization_id: str) -> list[dict[str, Any]]:
    return list(_collection("organization_links").find({"organization_id": organization_id}))
