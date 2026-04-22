from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import (
    get_current_user,
    require_permission,
    require_package_capability,
)
from app.schemas.organization import (
    AssignmentCreate,
    EndAssignmentPayload,
    LinkedOrganizationCreate,
    OrganizationNodeCreate,
    OrganizationPersonCreate,
    OrganizationProfileUpsert,
    ReplaceRoleSeatPayload,
    RoleSeatCreate,
    SupportRecordCreate,
    TransitionEventCreate,
)
from app.services.audit_log_service import write_audit_log
from app.services.organization_service import (
    create_assignment,
    create_linked_organization,
    create_organization_node,
    create_person,
    create_role_seat,
    create_support_record,
    create_transition,
    end_assignment,
    list_assignments,
    list_links,
    list_organization_nodes,
    list_organization_profiles,
    list_people,
    list_role_seats,
    list_support_records,
    list_transitions,
    replace_role_seat_assignment,
    upsert_organization_profile,
)

router = APIRouter(prefix="/organizations", tags=["Organizations"])


def _actor_user_id(user: dict[str, Any]) -> str:
    return str(user.get("id") or user.get("_id") or user.get("user_id") or "").strip()


def _audit(current_user: dict[str, Any], action: str, target_type: str, target_id: str, *, details: dict[str, Any]) -> None:
    write_audit_log(
        actor_user_id=_actor_user_id(current_user),
        actor_email=str(current_user.get("email") or "").strip().lower() or None,
        actor_name=str(current_user.get("full_name") or current_user.get("name") or "").strip() or None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )


def _require_org_lane(current_user: dict[str, Any]) -> None:
    require_package_capability(
        current_user,
        "can_open_org_intake",
        detail="Command Structure Network entitlement is required for organization routes.",
    )


@router.get("/profile")
def get_organization_profile(
    organization_id: str | None = None,
    current_user: dict[str, Any] = Depends(require_permission("projects.read")),
):
    _require_org_lane(current_user)
    return {"items": list_organization_profiles(organization_id)}


@router.post("/profile")
def post_organization_profile(
    payload: OrganizationProfileUpsert,
    current_user: dict[str, Any] = Depends(require_permission("uploads.write")),
):
    _require_org_lane(current_user)
    item = upsert_organization_profile(payload.model_dump(), actor_user_id=_actor_user_id(current_user))
    _audit(current_user, "organization.profile.upsert", "organization", payload.organization_id, details={"project_id": payload.project_id})
    return item


@router.get("/{org_id}/nodes")
def get_nodes(org_id: str, current_user: dict[str, Any] = Depends(require_permission("projects.read"))):
    _require_org_lane(current_user)
    return {"items": list_organization_nodes(org_id)}


@router.post("/{org_id}/nodes")
def post_nodes(
    org_id: str,
    payload: OrganizationNodeCreate,
    current_user: dict[str, Any] = Depends(require_permission("uploads.write")),
):
    _require_org_lane(current_user)
    try:
        item = create_organization_node(org_id, payload.model_dump(), actor_user_id=_actor_user_id(current_user))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _audit(current_user, "organization.node.create", "organization_node", str(item.get("node_key")), details={"organization_id": org_id})
    return item


@router.get("/{org_id}/role-seats")
def get_role_seats(org_id: str, current_user: dict[str, Any] = Depends(require_permission("projects.read"))):
    _require_org_lane(current_user)
    return {"items": list_role_seats(org_id)}


@router.post("/{org_id}/role-seats")
def post_role_seats(
    org_id: str,
    payload: RoleSeatCreate,
    current_user: dict[str, Any] = Depends(require_permission("uploads.write")),
):
    _require_org_lane(current_user)
    try:
        item = create_role_seat(org_id, payload.model_dump(), actor_user_id=_actor_user_id(current_user))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _audit(current_user, "organization.role_seat.create", "role_seat", str(item.get("role_key")), details={"organization_id": org_id})
    return item


@router.get("/{org_id}/people")
def get_people(org_id: str, current_user: dict[str, Any] = Depends(require_permission("projects.read"))):
    _require_org_lane(current_user)
    return {"items": list_people(org_id)}


@router.post("/{org_id}/people")
def post_people(
    org_id: str,
    payload: OrganizationPersonCreate,
    current_user: dict[str, Any] = Depends(require_permission("uploads.write")),
):
    _require_org_lane(current_user)
    try:
        item = create_person(org_id, payload.model_dump(), actor_user_id=_actor_user_id(current_user))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _audit(current_user, "organization.person.create", "organization_person", payload.person_id, details={"organization_id": org_id})
    return item


@router.get("/{org_id}/assignments")
def get_assignments(org_id: str, current_user: dict[str, Any] = Depends(require_permission("projects.read"))):
    _require_org_lane(current_user)
    return {"items": list_assignments(org_id)}


@router.post("/{org_id}/assignments")
def post_assignments(
    org_id: str,
    payload: AssignmentCreate,
    current_user: dict[str, Any] = Depends(require_permission("uploads.write")),
):
    _require_org_lane(current_user)
    try:
        item = create_assignment(org_id, payload.model_dump(), actor_user_id=_actor_user_id(current_user))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _audit(current_user, "organization.assignment.create", "assignment", payload.assignment_id, details={"organization_id": org_id, "sensitive": True})
    return item


@router.post("/{org_id}/assignments/{assignment_id}/end")
def end_assignment_route(
    org_id: str,
    assignment_id: str,
    payload: EndAssignmentPayload,
    current_user: dict[str, Any] = Depends(require_permission("uploads.write")),
):
    _require_org_lane(current_user)
    try:
        item = end_assignment(
            org_id,
            assignment_id,
            end_date=payload.end_date,
            status=payload.status,
            notes=payload.notes,
            actor_user_id=_actor_user_id(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _audit(current_user, "organization.assignment.end", "assignment", assignment_id, details={"organization_id": org_id, "sensitive": True})
    return item


@router.post("/{org_id}/role-seats/{role_seat_id}/replace")
def replace_role_seat(
    org_id: str,
    role_seat_id: str,
    payload: ReplaceRoleSeatPayload,
    current_user: dict[str, Any] = Depends(require_permission("uploads.write")),
):
    _require_org_lane(current_user)
    try:
        item = replace_role_seat_assignment(
            org_id,
            role_seat_id,
            payload.model_dump(),
            actor_user_id=_actor_user_id(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _audit(current_user, "organization.role_seat.replace", "role_seat", role_seat_id, details={"organization_id": org_id, "sensitive": True})
    return item


@router.get("/{org_id}/transitions")
def get_transitions(org_id: str, current_user: dict[str, Any] = Depends(require_permission("projects.read"))):
    _require_org_lane(current_user)
    return {"items": list_transitions(org_id)}


@router.post("/{org_id}/transitions")
def post_transitions(
    org_id: str,
    payload: TransitionEventCreate,
    current_user: dict[str, Any] = Depends(require_permission("uploads.write")),
):
    _require_org_lane(current_user)
    try:
        item = create_transition(org_id, payload.model_dump(), actor_user_id=_actor_user_id(current_user))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _audit(current_user, "organization.transition.create", "transition", payload.transition_id, details={"organization_id": org_id, "sensitive": True})
    return item


@router.get("/{org_id}/support-records")
def get_support_records(org_id: str, current_user: dict[str, Any] = Depends(require_permission("projects.read"))):
    _require_org_lane(current_user)
    return {"items": list_support_records(org_id)}


@router.post("/{org_id}/support-records")
def post_support_records(
    org_id: str,
    payload: SupportRecordCreate,
    current_user: dict[str, Any] = Depends(require_permission("uploads.write")),
):
    _require_org_lane(current_user)
    try:
        item = create_support_record(org_id, payload.model_dump(), actor_user_id=_actor_user_id(current_user))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if payload.sensitive:
        _audit(current_user, "organization.support_record.sensitive_access", "support_record", payload.support_record_id, details={"organization_id": org_id, "privacy_level": payload.privacy_level})
    _audit(current_user, "organization.support_record.create", "support_record", payload.support_record_id, details={"organization_id": org_id, "privacy_level": payload.privacy_level})
    return item


@router.get("/{org_id}/links")
def get_links(org_id: str, current_user: dict[str, Any] = Depends(require_permission("projects.read"))):
    _require_org_lane(current_user)
    return {"items": list_links(org_id)}


@router.post("/{org_id}/links")
def post_links(
    org_id: str,
    payload: LinkedOrganizationCreate,
    current_user: dict[str, Any] = Depends(require_permission("uploads.write")),
):
    _require_org_lane(current_user)
    try:
        item = create_linked_organization(org_id, payload.model_dump(), actor_user_id=_actor_user_id(current_user))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _audit(current_user, "organization.link.create", "organization_link", f"{org_id}:{payload.linked_organization_id}:{payload.link_type}", details={"organization_id": org_id})
    return item
