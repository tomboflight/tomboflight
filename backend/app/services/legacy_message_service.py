from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from bson import ObjectId
from pymongo.collection import Collection

from app.database import get_database
from app.schemas.legacy_message import LegacyMessageCreate, LegacyMessageUpdate
from app.services.audit_log_service import create_audit_log

VALID_RELEASE_TRIGGERS = {
    "on_death",
    "on_date",
    "on_age_milestone",
    "open_when",
    "immediate",
    "manual",
}
SCHEDULED_RELEASE_TRIGGERS = {
    "on_death",
    "on_date",
    "on_age_milestone",
    "open_when",
}


def _col(name: str) -> Collection[dict[str, Any]]:
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")
    return cast(Collection[dict[str, Any]], db[name])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> str:
    return _utcnow().isoformat()


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _str_id(value: Any) -> str:
    if isinstance(value, ObjectId):
        return str(value)
    return _normalize(value)


def _id_query(message_id: str) -> dict[str, Any]:
    if ObjectId.is_valid(message_id):
        return {"_id": ObjectId(message_id)}
    return {"_id": message_id}


def _find_by_id(message_id: str) -> dict[str, Any] | None:
    return cast(
        dict[str, Any] | None, _col("legacy_messages").find_one(_id_query(message_id))
    )


def _serialize(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not doc:
        return None
    result = dict(doc)
    result["id"] = _str_id(doc.get("_id"))
    result.pop("_id", None)
    return result


def _assert_authorized_project(
    doc_or_project_id: dict[str, Any] | str,
    *,
    authorized_project_id: str,
) -> str:
    project_id = (
        _normalize(doc_or_project_id.get("project_id"))
        if isinstance(doc_or_project_id, dict)
        else _normalize(doc_or_project_id)
    )
    normalized_authorized = _normalize(authorized_project_id)
    if (
        not project_id
        or not normalized_authorized
        or project_id != normalized_authorized
    ):
        raise PermissionError("Legacy message does not belong to the active workspace.")
    return project_id


def _parse_release_datetime(value: Any) -> datetime:
    raw_value = _normalize(value)
    if not raw_value:
        raise ValueError("release_value is required for an on_date message.")
    try:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "release_value must be a valid ISO-8601 date or timestamp."
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validate_release_configuration(
    doc: dict[str, Any],
) -> tuple[str, str | None, datetime | None]:
    trigger = _normalize(doc.get("release_trigger")).lower()
    if trigger not in VALID_RELEASE_TRIGGERS:
        raise ValueError("Legacy message release_trigger is invalid.")

    raw_release_value = _normalize(doc.get("release_value"))
    release_value = raw_release_value or None
    release_at: datetime | None = None

    if trigger == "on_date":
        release_at = _parse_release_datetime(release_value)
    elif trigger == "on_age_milestone":
        if not raw_release_value.isdigit() or not 1 <= int(raw_release_value) <= 150:
            raise ValueError("release_value must be an age from 1 through 150.")
    elif trigger == "open_when":
        if not raw_release_value:
            raise ValueError("release_value is required for an open_when message.")
    elif raw_release_value:
        raise ValueError(f"release_value is not allowed for a {trigger} message.")

    return trigger, release_value, release_at


def _normalize_recipients(doc: dict[str, Any]) -> list[str]:
    recipients: list[str] = []
    raw_recipients = doc.get("named_recipients")
    if not isinstance(raw_recipients, list):
        raise ValueError("named_recipients must be a list of user ids.")
    for value in raw_recipients:
        recipient_id = _normalize(value)
        if not recipient_id:
            raise ValueError("named_recipients cannot contain blank user ids.")
        if recipient_id not in recipients:
            recipients.append(recipient_id)
    return recipients


def _validate_recipient_configuration(doc: dict[str, Any]) -> list[str]:
    recipient_scope = _normalize(doc.get("recipient_scope")).lower()
    recipients = _normalize_recipients(doc)
    if recipient_scope != "named_list":
        raise ValueError(
            "Only named_list recipient identity is currently supported for message release."
        )
    owner_user_id = _normalize(doc.get("owner_user_id"))
    authorized_recipients = [
        recipient for recipient in recipients if recipient != owner_user_id
    ]
    if not authorized_recipients:
        raise ValueError(
            "At least one named recipient other than the owner is required."
        )
    return authorized_recipients


def _audit_transition(
    *,
    action: str,
    actor_user_id: str | None,
    doc: dict[str, Any],
    from_status: str,
    to_status: str,
    release_source: str | None = None,
) -> None:
    details: dict[str, Any] = {
        "project_id": _normalize(doc.get("project_id")),
        "release_trigger": _normalize(doc.get("release_trigger")).lower(),
        "from_status": from_status,
        "to_status": to_status,
    }
    if release_source:
        details["release_source"] = release_source
    create_audit_log(
        action,
        _normalize(actor_user_id) or None,
        "legacy_message",
        _str_id(doc.get("_id")),
        details,
    )


def get_legacy_message_access_descriptor(message_id: str) -> dict[str, str] | None:
    doc = _find_by_id(message_id)
    if not doc:
        return None
    return {
        "id": _str_id(doc.get("_id")),
        "project_id": _normalize(doc.get("project_id")),
        "release_trigger": _normalize(doc.get("release_trigger")).lower(),
        "status": _normalize(doc.get("status")).lower(),
    }


def create_legacy_message(
    payload: LegacyMessageCreate,
    owner_user_id: str,
    *,
    authorized_project_id: str,
) -> dict[str, Any]:
    project_id = _assert_authorized_project(
        payload.project_id,
        authorized_project_id=authorized_project_id,
    )
    normalized_owner_user_id = _normalize(owner_user_id)
    if not normalized_owner_user_id:
        raise PermissionError("Authenticated owner identity is required.")

    now = _now()
    doc: dict[str, Any] = {
        **payload.model_dump(),
        "project_id": project_id,
        "owner_user_id": normalized_owner_user_id,
        "status": "draft",
        "activated_at": None,
        "released_at": None,
        "release_source": None,
        "created_at": now,
        "updated_at": now,
    }
    _validate_release_configuration(doc)
    _normalize_recipients(doc)

    result = _col("legacy_messages").insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc) or {}


def list_legacy_messages(
    project_id: str,
    owner_user_id: str,
    *,
    authorized_project_id: str,
) -> list[dict[str, Any]]:
    normalized_project_id = _assert_authorized_project(
        project_id,
        authorized_project_id=authorized_project_id,
    )
    cursor = (
        _col("legacy_messages")
        .find(
            {
                "project_id": normalized_project_id,
                "owner_user_id": _normalize(owner_user_id),
            }
        )
        .sort("created_at", -1)
    )
    return [_serialize(cast(dict[str, Any], doc)) for doc in cursor if doc]  # type: ignore[misc]


def _release_due_on_date_message(
    doc: dict[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    message_id = _str_id(doc.get("_id"))
    released_at = now.isoformat()
    result = _col("legacy_messages").update_one(
        {**_id_query(message_id), "status": "active"},
        {
            "$set": {
                "status": "released",
                "released_at": released_at,
                "release_source": "scheduled_date",
                "updated_at": released_at,
            }
        },
    )
    refreshed = _find_by_id(message_id) or doc
    if int(getattr(result, "modified_count", 0) or 0) == 1:
        _audit_transition(
            action="legacy_message_released",
            actor_user_id=None,
            doc=refreshed,
            from_status="active",
            to_status="released",
            release_source="scheduled_date",
        )
    return refreshed


def get_legacy_message(
    message_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str,
) -> dict[str, Any] | None:
    doc = _find_by_id(message_id)
    if not doc:
        return None
    _assert_authorized_project(doc, authorized_project_id=authorized_project_id)

    normalized_requesting_user_id = _normalize(requesting_user_id)
    owner_user_id = _normalize(doc.get("owner_user_id"))
    if owner_user_id and owner_user_id == normalized_requesting_user_id:
        return _serialize(doc)

    try:
        trigger, _release_value, release_at = _validate_release_configuration(doc)
        recipients = _validate_recipient_configuration(doc)
    except ValueError as exc:
        raise PermissionError("This message has not been released.") from exc

    if normalized_requesting_user_id not in recipients:
        raise PermissionError("Access denied to this message.")

    status = _normalize(doc.get("status")).lower()
    now = _utcnow()
    if trigger == "on_date":
        if release_at is None or now < release_at:
            raise PermissionError("This message has not been released.")
        if status == "active":
            doc = _release_due_on_date_message(doc, now=now)
            status = _normalize(doc.get("status")).lower()

    if status != "released":
        raise PermissionError("This message has not been released.")
    return _serialize(doc)


def update_legacy_message(
    message_id: str,
    updates: LegacyMessageUpdate,
    requesting_user_id: str,
    *,
    authorized_project_id: str,
) -> dict[str, Any] | None:
    doc = _find_by_id(message_id)
    if not doc:
        raise ValueError("Legacy message not found.")
    _assert_authorized_project(doc, authorized_project_id=authorized_project_id)

    owner_user_id = _normalize(doc.get("owner_user_id"))
    if owner_user_id != _normalize(requesting_user_id):
        raise PermissionError("Only the owner can update this message.")
    if _normalize(doc.get("status")).lower() != "draft":
        raise ValueError("Only draft messages can be updated.")

    update_data = updates.model_dump(exclude_unset=True)
    candidate = {**doc, **update_data}
    _validate_release_configuration(candidate)
    candidate_recipients = _normalize_recipients(candidate)
    candidate_scope = _normalize(candidate.get("recipient_scope")).lower()
    if candidate_scope == "named_list" and not candidate_recipients:
        raise ValueError(
            "named_recipients is required when recipient_scope is named_list."
        )
    if candidate_scope != "named_list" and candidate_recipients:
        raise ValueError(
            "named_recipients is only allowed when recipient_scope is named_list."
        )

    if "named_recipients" in update_data:
        update_data["named_recipients"] = candidate_recipients
    update_data["updated_at"] = _now()
    _col("legacy_messages").update_one(_id_query(message_id), {"$set": update_data})
    return _serialize(_find_by_id(message_id))


def delete_legacy_message(
    message_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str,
) -> bool:
    doc = _find_by_id(message_id)
    if not doc:
        raise ValueError("Legacy message not found.")
    _assert_authorized_project(doc, authorized_project_id=authorized_project_id)

    if _normalize(doc.get("owner_user_id")) != _normalize(requesting_user_id):
        raise PermissionError("Only the owner can delete this message.")
    if _normalize(doc.get("status")).lower() != "draft":
        raise ValueError("Only draft messages can be deleted.")

    _col("legacy_messages").delete_one(_id_query(message_id))
    return True


def activate_legacy_message(
    message_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str,
) -> dict[str, Any] | None:
    doc = _find_by_id(message_id)
    if not doc:
        raise ValueError("Legacy message not found.")
    _assert_authorized_project(doc, authorized_project_id=authorized_project_id)

    normalized_requesting_user_id = _normalize(requesting_user_id)
    if _normalize(doc.get("owner_user_id")) != normalized_requesting_user_id:
        raise PermissionError("Only the owner can activate this message.")
    if _normalize(doc.get("status")).lower() != "draft":
        raise ValueError("Only draft messages can be activated.")

    trigger, _release_value, release_at = _validate_release_configuration(doc)
    _validate_recipient_configuration(doc)
    now_dt = _utcnow()
    if trigger == "on_date" and (release_at is None or release_at <= now_dt):
        raise ValueError(
            "An on_date message must have a future release_value when activated."
        )

    now = now_dt.isoformat()
    next_status = "released" if trigger == "immediate" else "active"
    transition: dict[str, Any] = {
        "status": next_status,
        "activated_at": now,
        "updated_at": now,
    }
    if next_status == "released":
        transition.update(
            {
                "released_at": now,
                "release_source": "activation_immediate",
            }
        )

    result = _col("legacy_messages").update_one(
        {**_id_query(message_id), "status": "draft"},
        {"$set": transition},
    )
    if int(getattr(result, "modified_count", 0) or 0) != 1:
        raise ValueError("Legacy message activation state changed; retry the request.")

    updated = _find_by_id(message_id)
    if updated is None:
        raise RuntimeError("Activated legacy message could not be reloaded.")
    _audit_transition(
        action="legacy_message_activated",
        actor_user_id=normalized_requesting_user_id,
        doc=updated,
        from_status="draft",
        # Immediate messages transition atomically to released in storage, but
        # the audit trail still records the logical activation before release.
        to_status="active",
    )
    if next_status == "released":
        _audit_transition(
            action="legacy_message_released",
            actor_user_id=normalized_requesting_user_id,
            doc=updated,
            from_status="active",
            to_status="released",
            release_source="activation_immediate",
        )
    return _serialize(updated)


def release_legacy_message(
    message_id: str,
    requesting_user_id: str,
    *,
    authorized_project_id: str,
) -> dict[str, Any] | None:
    doc = _find_by_id(message_id)
    if not doc:
        raise ValueError("Legacy message not found.")
    _assert_authorized_project(doc, authorized_project_id=authorized_project_id)

    normalized_requesting_user_id = _normalize(requesting_user_id)
    if _normalize(doc.get("owner_user_id")) != normalized_requesting_user_id:
        raise PermissionError("Only the owner can release this message.")
    if _normalize(doc.get("status")).lower() != "active":
        raise ValueError("Only an active message can be released.")

    trigger, _release_value, _release_at = _validate_release_configuration(doc)
    _validate_recipient_configuration(doc)
    if trigger != "manual":
        raise ValueError("Only a manual message can be released through this endpoint.")

    now = _now()
    result = _col("legacy_messages").update_one(
        {**_id_query(message_id), "status": "active"},
        {
            "$set": {
                "status": "released",
                "released_at": now,
                "release_source": "manual_owner_release",
                "updated_at": now,
            }
        },
    )
    if int(getattr(result, "modified_count", 0) or 0) != 1:
        raise ValueError("Legacy message release state changed; retry the request.")

    updated = _find_by_id(message_id)
    if updated is None:
        raise RuntimeError("Released legacy message could not be reloaded.")
    _audit_transition(
        action="legacy_message_released",
        actor_user_id=normalized_requesting_user_id,
        doc=updated,
        from_status="active",
        to_status="released",
        release_source="manual_owner_release",
    )
    return _serialize(updated)
