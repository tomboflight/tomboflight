from __future__ import annotations

import logging
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, WebSocket, status

from app.core.admin_permission_registry import has_canonical_internal_admin_authority
from app.core.security import decode_access_token
from app.core.websocket_manager import websocket_manager
from app.database import get_database
from app.dependencies.auth import (
    COOKIE_NAME,
    _allowed_cookie_auth_origins,
    _normalize_origin,
)
from app.services.auth_service import get_user_by_email, get_user_by_id
from app.services.project_membership_service import list_accessible_project_ids
from app.services.workspace_access_service import resolve_workspace_context


WS_EXPERIENCE_PATH = "/ws/experience"
WS_FAMILY_PATH = "/ws/family/{family_id}"
WS_PROJECT_PATH = "/ws/project/{project_id}"
WEBSOCKET_PATHS = [WS_EXPERIENCE_PATH, WS_FAMILY_PATH, WS_PROJECT_PATH]
PRESENCE_AUTHORIZATION_QUERY_LIMIT = 500

logger = logging.getLogger(__name__)


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _normalize_email(value: Any) -> str:
    return _normalize(value).lower()


def _current_user_id(user: dict[str, Any]) -> str:
    return _normalize(user.get("id") or user.get("_id") or user.get("user_id"))


def _current_user_email(user: dict[str, Any]) -> str:
    return _normalize_email(user.get("email"))


def _current_user_name(user: dict[str, Any]) -> str:
    return _normalize(user.get("full_name") or user.get("name"))


def _room_name(channel_type: str, channel_id: str = "") -> str:
    normalized_id = _normalize(channel_id)
    return f"{channel_type}:{normalized_id}" if normalized_id else channel_type


def _mongo_id_candidates(values: set[str]) -> list[Any]:
    candidates: list[Any] = []
    for value in sorted(values):
        normalized = _normalize(value)
        if not normalized:
            continue
        candidates.append(normalized)
        if ObjectId.is_valid(normalized):
            candidates.append(ObjectId(normalized))
    return candidates


def _record_id(document: dict[str, Any], *keys: str) -> str:
    for key in keys:
        normalized = _normalize(document.get(key))
        if normalized:
            return normalized
    return ""


def _candidate_presence_workspace_ids(
    current_user: dict[str, Any],
) -> tuple[set[str], set[str]]:
    """Collect user-linked workspace ids without inspecting global presence rooms."""

    user_id = _current_user_id(current_user)
    email = _current_user_email(current_user)
    full_name = _current_user_name(current_user)
    project_ids: set[str] = {
        _normalize(current_user.get("active_project_id")),
        _normalize(current_user.get("activeProjectId")),
    }
    family_ids: set[str] = {
        _normalize(current_user.get("active_family_id")),
        _normalize(current_user.get("activeFamilyId")),
    }
    project_ids.discard("")
    family_ids.discard("")

    try:
        db = get_database()
    except RuntimeError:
        return project_ids, family_ids
    if db is None:
        return project_ids, family_ids

    try:
        project_ids.update(
            list_accessible_project_ids(
                user_id=user_id,
                email=email,
                active_only=True,
            )
        )
    except Exception:
        logger.warning("Unable to enumerate active project memberships for presence status.")

    member_filters: list[dict[str, Any]] = []
    if user_id:
        member_filters.append({"user_id": user_id})
    if email:
        member_filters.extend([{"email": email}, {"user_email": email}])
    if member_filters:
        memberships = (
            db["project_members"]
            .find(
                {
                    "$or": member_filters,
                    "status": {"$ne": "suspended"},
                },
                {"project_id": 1},
            )
            .limit(PRESENCE_AUTHORIZATION_QUERY_LIMIT)
        )
        for membership in memberships:
            project_id = _normalize(membership.get("project_id"))
            if project_id:
                project_ids.add(project_id)

    owner_filters: list[dict[str, Any]] = []
    if user_id:
        owner_filters.append({"owner_user_id": user_id})
    if email:
        owner_filters.append({"owner_email": email})
    if owner_filters:
        projects = (
            db["projects"]
            .find(
                {"$or": owner_filters},
                {"_id": 1, "id": 1, "project_id": 1, "family_id": 1},
            )
            .limit(PRESENCE_AUTHORIZATION_QUERY_LIMIT)
        )
        for project in projects:
            project_id = _record_id(project, "_id", "id", "project_id")
            family_id = _record_id(project, "family_id")
            if project_id:
                project_ids.add(project_id)
            if family_id:
                family_ids.add(family_id)

    family_filters: list[dict[str, Any]] = []
    if user_id:
        family_filters.extend(
            [
                {"owner_user_id": user_id},
                {"shared_with_user_ids": user_id},
            ]
        )
    if email:
        family_filters.extend(
            [
                {"owner_email": email},
                {"shared_with_emails": email},
                {"created_by": email},
            ]
        )
    if full_name:
        family_filters.append({"created_by": full_name})
    if family_filters:
        families = (
            db["families"]
            .find(
                {"$or": family_filters},
                {"_id": 1, "id": 1, "family_id": 1, "project_id": 1},
            )
            .limit(PRESENCE_AUTHORIZATION_QUERY_LIMIT)
        )
        for family in families:
            family_id = _record_id(family, "_id", "id", "family_id")
            project_id = _record_id(family, "project_id")
            if family_id:
                family_ids.add(family_id)
            if project_id:
                project_ids.add(project_id)

    # Load canonical project records so memberships and active-project hints can
    # resolve projects that store their family link on the project document.
    if project_ids:
        id_candidates = _mongo_id_candidates(project_ids)
        projects = (
            db["projects"]
            .find(
                {
                    "$or": [
                        {"_id": {"$in": id_candidates}},
                        {"id": {"$in": id_candidates}},
                        {"project_id": {"$in": id_candidates}},
                    ]
                },
                {"_id": 1, "id": 1, "project_id": 1, "family_id": 1},
            )
            .limit(PRESENCE_AUTHORIZATION_QUERY_LIMIT)
        )
        for project in projects:
            project_id = _record_id(project, "_id", "id", "project_id")
            family_id = _record_id(project, "family_id")
            if project_id:
                project_ids.add(project_id)
            if family_id:
                family_ids.add(family_id)

    # Load canonical family records so active-family hints can resolve projects
    # that store their relationship on the family document.
    if family_ids:
        id_candidates = _mongo_id_candidates(family_ids)
        families = (
            db["families"]
            .find(
                {
                    "$or": [
                        {"_id": {"$in": id_candidates}},
                        {"id": {"$in": id_candidates}},
                        {"family_id": {"$in": id_candidates}},
                    ]
                },
                {"_id": 1, "id": 1, "family_id": 1, "project_id": 1},
            )
            .limit(PRESENCE_AUTHORIZATION_QUERY_LIMIT)
        )
        for family in families:
            family_id = _record_id(family, "_id", "id", "family_id")
            project_id = _record_id(family, "project_id")
            if family_id:
                family_ids.add(family_id)
            if project_id:
                project_ids.add(project_id)

    # Resolve family rooms attached to the user's projects without iterating
    # through the global WebSocket room snapshot.
    if project_ids:
        families = (
            db["families"]
            .find(
                {"project_id": {"$in": _mongo_id_candidates(project_ids)}},
                {"_id": 1, "id": 1, "family_id": 1, "project_id": 1},
            )
            .limit(PRESENCE_AUTHORIZATION_QUERY_LIMIT)
        )
        for family in families:
            family_id = _record_id(family, "_id", "id", "family_id")
            project_id = _record_id(family, "project_id")
            if family_id:
                family_ids.add(family_id)
            if project_id:
                project_ids.add(project_id)

    # Resolve projects that point at a user-linked family.
    if family_ids:
        projects = (
            db["projects"]
            .find(
                {"family_id": {"$in": _mongo_id_candidates(family_ids)}},
                {"_id": 1, "id": 1, "project_id": 1, "family_id": 1},
            )
            .limit(PRESENCE_AUTHORIZATION_QUERY_LIMIT)
        )
        for project in projects:
            project_id = _record_id(project, "_id", "id", "project_id")
            family_id = _record_id(project, "family_id")
            if project_id:
                project_ids.add(project_id)
            if family_id:
                family_ids.add(family_id)

    return project_ids, family_ids


def _add_workspace_context_channels(
    channels: set[str],
    context: dict[str, Any],
) -> None:
    project = context.get("project") or {}
    family = context.get("family") or {}
    project_id = _record_id(project, "_id", "id", "project_id")
    family_id = _record_id(family, "_id", "id", "family_id")
    if project_id:
        channels.add(_room_name("project", project_id))
    if family_id:
        channels.add(_room_name("family", family_id))


def resolve_authorized_presence_channels(
    current_user: dict[str, Any],
) -> set[str]:
    """Return only workspace rooms the current identity may observe."""

    if has_canonical_internal_admin_authority(current_user):
        return set(websocket_manager.snapshot())

    try:
        project_ids, family_ids = _candidate_presence_workspace_ids(current_user)
    except Exception:
        logger.warning(
            "Unable to collect tenant-scoped presence candidates.",
            exc_info=True,
        )
        return set()

    authorized_channels: set[str] = set()

    for project_id in sorted(project_ids)[:PRESENCE_AUTHORIZATION_QUERY_LIMIT]:
        try:
            context = resolve_workspace_context(
                current_user,
                project_id=project_id,
            )
        except HTTPException:
            continue
        except Exception:
            logger.warning(
                "Unable to validate project presence scope.",
                exc_info=True,
            )
            continue
        _add_workspace_context_channels(authorized_channels, context)

    for family_id in sorted(family_ids)[:PRESENCE_AUTHORIZATION_QUERY_LIMIT]:
        try:
            context = resolve_workspace_context(
                current_user,
                family_id=family_id,
            )
        except HTTPException:
            continue
        except Exception:
            logger.warning(
                "Unable to validate family presence scope.",
                exc_info=True,
            )
            continue
        _add_workspace_context_channels(authorized_channels, context)

    return authorized_channels


def websocket_paths() -> list[str]:
    return list(WEBSOCKET_PATHS)


def build_presence_status(current_user: dict[str, Any]) -> dict[str, Any]:
    all_channels = websocket_manager.snapshot()
    if has_canonical_internal_admin_authority(current_user):
        channels = dict(all_channels)
    else:
        authorized_channels = resolve_authorized_presence_channels(current_user)
        channels = {
            room: count
            for room, count in all_channels.items()
            if room in authorized_channels
        }
    return {
        "status": "live",
        "active_connections": sum(channels.values()),
        "channels": channels,
        "websocket_paths": websocket_paths(),
    }


def build_presence_overview(*, project_id: str = "", family_id: str = "") -> dict[str, Any]:
    room_counts = websocket_manager.snapshot()
    return {
        "status": "live",
        "active_connections": room_counts.get(_room_name("project", project_id), 0)
        + room_counts.get(_room_name("family", family_id), 0),
        "project_channel": _room_name("project", project_id) if project_id else None,
        "family_channel": _room_name("family", family_id) if family_id else None,
        "experience_channel": "experience",
        "websocket_paths": websocket_paths(),
    }


def authenticate_presence_user(token: str) -> dict[str, Any]:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid websocket token.")
    if _normalize(payload.get("purpose")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MFA and account-action tokens cannot open websocket sessions.",
        )

    user_id = _normalize(payload.get("user_id") or payload.get("id"))
    email = _normalize(payload.get("sub") or payload.get("email")).lower()

    user = get_user_by_id(user_id) if user_id else None
    if user is None and email:
        user = get_user_by_email(email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Websocket user could not be resolved.",
        )

    actual_user_id = _current_user_id(user)
    actual_email = _normalize(user.get("email")).lower()
    if user_id and actual_user_id and user_id != actual_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid websocket token identity.",
        )
    if email and actual_email and email != actual_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid websocket token identity.",
        )

    status_value = _normalize(user.get("status")).lower()
    if status_value not in {"", "active"} or user.get("login_enabled") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Websocket user is inactive.",
        )

    token_version = _normalize(payload.get("tv"))
    user_token_version = _normalize(user.get("session_token_version") or 0)
    legacy_version_allowed = token_version == "" and user_token_version == "0"
    if token_version != user_token_version and not legacy_version_allowed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Websocket session has been revoked.",
        )

    if bool(user.get("mfa_enabled")) and not bool(payload.get("mfa")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MFA verification is required for this websocket session.",
        )
    return user


def authenticate_presence_websocket(websocket: WebSocket) -> dict[str, Any]:
    cookie_token = _normalize(websocket.cookies.get(COOKIE_NAME))
    query_token = _normalize(websocket.query_params.get("token"))
    if cookie_token:
        origin = _normalize_origin(websocket.headers.get("origin"))
        if not origin or origin not in _allowed_cookie_auth_origins():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Origin is not allowed for cookie-authenticated websocket.",
            )
    token = cookie_token or query_token
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Websocket authentication token is required.")
    return authenticate_presence_user(token)


def ensure_presence_scope(
    current_user: dict[str, Any],
    *,
    project_id: str = "",
    family_id: str = "",
) -> None:
    if project_id:
        resolve_workspace_context(current_user, project_id=project_id)
    elif family_id:
        resolve_workspace_context(current_user, family_id=family_id)


async def connect_presence_channel(websocket: WebSocket, room: str, payload: dict[str, Any]) -> None:
    await websocket_manager.connect(room, websocket)
    await websocket_manager.send_json(websocket, payload)


async def disconnect_presence_channel(websocket: WebSocket, room: str) -> None:
    await websocket_manager.disconnect(room, websocket)


async def broadcast_presence_event(room: str, payload: dict[str, Any]) -> None:
    await websocket_manager.broadcast(room, payload)
