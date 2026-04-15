from __future__ import annotations

from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.schemas.household_access import (
    HouseholdInviteAccept,
    HouseholdInviteCreate,
    HouseholdMemberRoleUpdate,
    build_invite_response,
    build_membership_response,
)
from app.services.household_access_service import (
    accept_household_invite,
    create_household_invite,
    list_my_memberships,
    list_project_invites,
    list_project_members,
    revoke_household_invite,
    revoke_membership,
    update_member_role,
)
from app.database import get_database
from app.services.project_membership_service import get_project_access_snapshot

router = APIRouter(prefix="/workspace-access", tags=["Workspace Access"])


def _current_user_id(user: dict[str, Any]) -> str:
    raw_id = user.get("id") or user.get("_id") or user.get("user_id")
    if raw_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing.",
        )
    return str(raw_id)


def _assert_project_access(project_id: str, current_user: dict[str, Any]) -> None:
    db = get_database()
    project_stub = None
    if db is not None and ObjectId.is_valid(project_id):
        project_stub = db["projects"].find_one({"_id": ObjectId(project_id)})
    project_stub = project_stub or {"_id": project_id}
    snapshot = get_project_access_snapshot(
        project_stub,
        user_id=_current_user_id(current_user),
        email=str(current_user.get("email") or "").strip().lower(),
    )
    if not snapshot.get("accessible"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this workspace.",
        )


@router.get("/my-memberships")
def get_my_memberships(current_user: dict[str, Any] = Depends(get_current_user)):
    items = list_my_memberships(current_user)
    return {"items": [build_membership_response(item) for item in items]}


@router.get("/project/{project_id}/members")
def get_project_members(project_id: str, current_user: dict[str, Any] = Depends(get_current_user)):
    _assert_project_access(project_id, current_user)
    items = list_project_members(project_id)
    return {"items": [build_membership_response(item) for item in items]}


@router.get("/project/{project_id}/invites")
def get_project_invites(project_id: str, current_user: dict[str, Any] = Depends(get_current_user)):
    _assert_project_access(project_id, current_user)
    invites = list_project_invites(project_id)
    return {"items": [build_invite_response(item) for item in invites]}


@router.post("/project/{project_id}/invites", status_code=status.HTTP_201_CREATED)
def create_invite(
    project_id: str,
    payload: HouseholdInviteCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        invite = create_household_invite(
            project_id=project_id,
            actor_user=current_user,
            email=payload.email,
            member_role=payload.member_role,
            relationship_scope=payload.relationship_scope,
            privacy_scope=payload.privacy_scope,
            notes=payload.notes,
            expires_in_days=payload.expires_in_days,
            max_uses=payload.max_uses,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return build_invite_response(invite)


@router.post("/invites/accept")
def accept_invite(
    payload: HouseholdInviteAccept,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        membership = accept_household_invite(invite_key=payload.invite_key, user=current_user)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return build_membership_response(membership)


@router.post("/invites/{invite_id}/revoke")
def revoke_invite(invite_id: str, current_user: dict[str, Any] = Depends(get_current_user)):
    try:
        invite = revoke_household_invite(invite_id=invite_id, actor_user=current_user)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found.")
    return build_invite_response(invite)


@router.post("/project/{project_id}/members/{membership_id}/role")
def change_member_role(
    project_id: str,
    membership_id: str,
    payload: HouseholdMemberRoleUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        membership = update_member_role(
            project_id=project_id,
            membership_id=membership_id,
            member_role=payload.member_role,
            actor_user=current_user,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found.")
    return build_membership_response(membership)


@router.post("/project/{project_id}/members/{membership_id}/revoke")
def revoke_member(
    project_id: str,
    membership_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        membership = revoke_membership(
            project_id=project_id,
            membership_id=membership_id,
            actor_user=current_user,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found.")
    return build_membership_response(membership)
