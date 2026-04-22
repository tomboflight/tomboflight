from __future__ import annotations

import csv
from datetime import date
from io import StringIO
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response

from app.dependencies.auth import (
    get_current_user,
    require_permission,
    require_package_capability,
)
from app.schemas.organization import (
    AdminSeatInvitePayload,
    AssignmentCreate,
    EndAssignmentPayload,
    LinkedOrganizationCreate,
    OrganizationNotePayload,
    OrganizationNodeCreate,
    OrganizationPersonCreate,
    OrganizationProfileUpsert,
    ReplaceRoleSeatPayload,
    RoleSeatCreate,
    SupportRecordCreate,
    SupportRecordVerifyPayload,
    TransitionEventCreate,
    WhiteGloveRequestPayload,
)
from app.database import get_database
from app.services.project_membership_service import get_project_access_snapshot
from app.services.audit_log_service import write_audit_log
from app.services.organization_service import (
    create_admin_invite,
    create_assignment,
    create_linked_organization,
    create_organization_note,
    create_organization_node,
    create_person,
    create_role_seat,
    create_support_record,
    create_transition,
    create_white_glove_request,
    end_assignment,
    export_command_roster,
    get_historical_snapshot,
    get_officer_wall,
    get_role_seat_succession,
    get_succession_timeline,
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
    verify_support_record,
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


def _require_org_project_access(organization_id: str, project_id: str, current_user: dict[str, Any]) -> None:
    db = get_database()
    project = db["projects"].find_one({"_id": project_id})
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    project_org = str(project.get("organization_id") or "").strip()
    if project_org != organization_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project is not mapped to the requested organization.")
    snapshot = get_project_access_snapshot(
        project,
        user_id=_actor_user_id(current_user),
        email=str(current_user.get("email") or ""),
    )
    if not bool(snapshot.get("accessible")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace/project access is required.")


def _command_structure_button_matrix() -> list[dict[str, Any]]:
    return [
        {
            "button": "Create Organization Profile",
            "status": "live",
            "route_service": "POST /organizations/profile -> upsert_organization_profile",
            "permission_gate": "uploads.write",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "organization.profile.upsert",
            "duplicate_prevention_behavior": "Upsert by organization_id; updates existing profile instead of creating duplicates.",
            "error_state": "400 validation errors; 403 permission denied; 401 unauthenticated.",
        },
        {
            "button": "Choose Organization Template",
            "status": "live",
            "route_service": "GET /packages/organization-templates -> get_organization_template_catalog",
            "permission_gate": "none (public catalog route)",
            "entitlement_gate": "none",
            "audit_behavior": "none",
            "duplicate_prevention_behavior": "Read-only template catalog.",
            "error_state": "N/A for normal reads.",
        },
        {
            "button": "Add Organization Node",
            "status": "live",
            "route_service": "POST /organizations/{org_id}/nodes -> create_organization_node",
            "permission_gate": "uploads.write",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "organization.node.create",
            "duplicate_prevention_behavior": "Unique organization_id + node_key index and node cap limit enforcement.",
            "error_state": "400 duplicate key or node cap exceeded; 403/401 auth errors.",
        },
        {
            "button": "Add Role Seat",
            "status": "live",
            "route_service": "POST /organizations/{org_id}/role-seats -> create_role_seat",
            "permission_gate": "uploads.write",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "organization.role_seat.create",
            "duplicate_prevention_behavior": "Unique organization_id + node_id + role_key index.",
            "error_state": "400 duplicate role seat; 403/401 auth errors.",
        },
        {
            "button": "Add Person / Officer",
            "status": "live",
            "route_service": "POST /organizations/{org_id}/people -> create_person",
            "permission_gate": "uploads.write",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "organization.person.create",
            "duplicate_prevention_behavior": "Unique organization_id + person_id index.",
            "error_state": "400 duplicate person_id in organization; 403/401 auth errors.",
        },
        {
            "button": "Assign Person to Role",
            "status": "live",
            "route_service": "POST /organizations/{org_id}/assignments -> create_assignment",
            "permission_gate": "uploads.write",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "organization.assignment.create (sensitive=true)",
            "duplicate_prevention_behavior": "Blocks duplicate current assignments for same role unless acting_or_interim=true.",
            "error_state": "400 duplicate/invalid assignment; 403/401 auth errors.",
        },
        {
            "button": "End Term / Mark Former",
            "status": "live",
            "route_service": "POST /organizations/{org_id}/assignments/{assignment_id}/end -> end_assignment",
            "permission_gate": "uploads.write",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "organization.assignment.end (sensitive=true)",
            "duplicate_prevention_behavior": "Idempotent target assignment update; no extra assignment is created.",
            "error_state": "400 assignment not found or invalid payload; 403/401 auth errors.",
        },
        {
            "button": "Replace Leader / Officer",
            "status": "live",
            "route_service": "POST /organizations/{org_id}/role-seats/{role_seat_id}/replace -> replace_role_seat_assignment",
            "permission_gate": "uploads.write",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "organization.role_seat.replace (sensitive=true)",
            "duplicate_prevention_behavior": "Ends existing current assignment and creates a new assignment atomically in service flow.",
            "error_state": "400 invalid replacement payload; 403/401 auth errors.",
        },
        {
            "button": "Mark Retired / Emeritus / Transferred / Deceased",
            "status": "live",
            "route_service": "POST /organizations/{org_id}/assignments/{assignment_id}/end (status field) + POST /organizations/{org_id}/transitions",
            "permission_gate": "uploads.write",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "organization.assignment.end and organization.transition.create",
            "duplicate_prevention_behavior": "Targets existing assignment/transition ids; no automatic duplicate generation.",
            "error_state": "400 assignment not found or unsupported transition event_type; 403/401 auth errors.",
        },
        {
            "button": "Add Transition Event",
            "status": "live",
            "route_service": "POST /organizations/{org_id}/transitions -> create_transition",
            "permission_gate": "uploads.write",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "organization.transition.create (sensitive=true)",
            "duplicate_prevention_behavior": "Caller-provided transition_id must remain unique in UI workflow.",
            "error_state": "400 unsupported transition event_type or malformed payload; 403/401 auth errors.",
        },
        {
            "button": "Upload Support Record",
            "status": "live",
            "route_service": "POST /organizations/{org_id}/support-records -> create_support_record",
            "permission_gate": "uploads.write",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "organization.support_record.create (+ sensitive_access audit for sensitive=true)",
            "duplicate_prevention_behavior": "Unique organization_id + support_record_id index and support record cap (25).",
            "error_state": "400 upload cap reached or duplicate support_record_id; 403/401 auth errors.",
        },
        {
            "button": "Verify Support Record",
            "status": "live",
            "route_service": "POST /organizations/{org_id}/support-records/{support_record_id}/verify -> verify_support_record",
            "permission_gate": "uploads.write",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "organization.support_record.verify",
            "duplicate_prevention_behavior": "Idempotent record-level status update; retries overwrite same support record instead of creating duplicates.",
            "error_state": "400 invalid status or record not found; 403/401 auth errors.",
        },
        {
            "button": "Open Leadership Viewer",
            "status": "live",
            "route_service": "GET /viewer/manifest?project_id={project_id} -> build_viewer_manifest",
            "permission_gate": "authenticated user",
            "entitlement_gate": "can_use_viewer or can_use_secure_share_viewer",
            "audit_behavior": "none in this route",
            "duplicate_prevention_behavior": "Read-only manifest request.",
            "error_state": "404 when requested project is not found; 403 for missing viewer capability.",
        },
        {
            "button": "View Current Command Structure",
            "status": "live",
            "route_service": "GET /viewer/manifest (organization mode: current_command_view available=true)",
            "permission_gate": "authenticated user",
            "entitlement_gate": "can_use_viewer or can_use_secure_share_viewer",
            "audit_behavior": "none in this route",
            "duplicate_prevention_behavior": "Read-only view mode.",
            "error_state": "404/403 viewer manifest errors.",
        },
        {
            "button": "View Historical Date",
            "status": "live",
            "route_service": "GET /organizations/{org_id}/viewer/historical?project_id={project_id}&date=YYYY-MM-DD -> get_historical_snapshot",
            "permission_gate": "projects.read",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "none",
            "duplicate_prevention_behavior": "Read-only snapshot endpoint based on assignment tenure.",
            "error_state": "400 invalid date or project mismatch; 403/401 auth errors.",
        },
        {
            "button": "View Succession Timeline",
            "status": "live",
            "route_service": "GET /organizations/{org_id}/role-seats/{role_seat_id}/succession + GET /organizations/{org_id}/viewer/succession-timeline",
            "permission_gate": "projects.read",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "none",
            "duplicate_prevention_behavior": "Read-only assignment history endpoint; no overwrite of historical records.",
            "error_state": "400 project mismatch; 403/401 auth errors.",
        },
        {
            "button": "View Officer Wall",
            "status": "live",
            "route_service": "GET /organizations/{org_id}/viewer/officer-wall?project_id={project_id}",
            "permission_gate": "projects.read",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "none",
            "duplicate_prevention_behavior": "Read-only aggregation of organization-native people and assignments.",
            "error_state": "400 project mismatch; 403/401 auth errors.",
        },
        {
            "button": "Link Organization",
            "status": "live",
            "route_service": "POST /organizations/{org_id}/links -> create_linked_organization",
            "permission_gate": "uploads.write",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "organization.link.create",
            "duplicate_prevention_behavior": "Unique organization_id + linked_organization_id + link_type index.",
            "error_state": "400 duplicate link; 403/401 auth errors.",
        },
        {
            "button": "Review Link Request",
            "status": "live",
            "route_service": "GET /link-requests/my-list + POST /link-requests/{request_id}/approve|reject|revoke",
            "permission_gate": "authenticated user (admin.access for global queue route only)",
            "entitlement_gate": "none",
            "audit_behavior": "Handled in link_request_service status updates.",
            "duplicate_prevention_behavior": "Service validates request state transitions and ownership/approver permissions.",
            "error_state": "400 invalid state transition; 403 unauthorized reviewer.",
        },
        {
            "button": "Export Command Roster",
            "status": "live",
            "route_service": "GET /organizations/{org_id}/exports/command-roster?project_id={project_id}&format=csv|json",
            "permission_gate": "projects.read",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "organization.command_roster.export",
            "duplicate_prevention_behavior": "Read-only export generation.",
            "error_state": "400 unsupported format or project mismatch; 403/401 auth errors.",
        },
        {
            "button": "Invite Admin Seat",
            "status": "live",
            "route_service": "POST /organizations/{org_id}/admin-seats/invite -> create_admin_invite",
            "permission_gate": "uploads.write",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "organization.admin_seat.invite",
            "duplicate_prevention_behavior": "Unique pending invite constraint by organization + project + email + role.",
            "error_state": "400 invalid payload or project mismatch; 403/401 auth errors.",
        },
        {
            "button": "Add Ops / Support Note",
            "status": "live",
            "route_service": "POST /organizations/{org_id}/notes -> create_organization_note",
            "permission_gate": "uploads.write",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "organization.note.create (+ internal note audit)",
            "duplicate_prevention_behavior": "Creates organization-scoped notes only; avoids non-organization note collections.",
            "error_state": "400 invalid payload or project mismatch; 403/401 auth errors.",
        },
        {
            "button": "Request White-Glove Review",
            "status": "live",
            "route_service": "POST /organizations/{org_id}/white-glove-review/request -> create_white_glove_request",
            "permission_gate": "uploads.write",
            "entitlement_gate": "can_open_org_intake",
            "audit_behavior": "organization.white_glove.request",
            "duplicate_prevention_behavior": "Single open request allowed per organization/project; retries return existing open case.",
            "error_state": "400 project mismatch; 403/401 auth errors.",
        },
    ]


@router.get("/profile")
def get_organization_profile(
    organization_id: str | None = None,
    current_user: dict[str, Any] = Depends(require_permission("projects.read")),
):
    _require_org_lane(current_user)
    return {"items": list_organization_profiles(organization_id)}


@router.get("/command-ui/buttons")
def get_command_structure_button_matrix(current_user: dict[str, Any] = Depends(require_permission("projects.read"))):
    _require_org_lane(current_user)
    return {
        "scope": "command_structure_network",
        "buttons": _command_structure_button_matrix(),
    }


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


@router.post("/{org_id}/support-records/{support_record_id}/verify")
def post_verify_support_record(
    org_id: str,
    support_record_id: str,
    payload: SupportRecordVerifyPayload,
    current_user: dict[str, Any] = Depends(require_permission("uploads.write")),
):
    _require_org_lane(current_user)
    try:
        item = verify_support_record(
            org_id,
            support_record_id,
            verification_status=payload.status,
            note=payload.note,
            actor_user_id=_actor_user_id(current_user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _audit(current_user, "organization.support_record.verify", "support_record", support_record_id, details={"organization_id": org_id, "status": payload.status})
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


@router.get("/{org_id}/viewer/historical")
def get_viewer_historical(
    org_id: str,
    project_id: str = Query(..., min_length=1),
    date_value: date = Query(..., alias="date"),
    current_user: dict[str, Any] = Depends(require_permission("projects.read")),
):
    _require_org_lane(current_user)
    _require_org_project_access(org_id, project_id, current_user)
    return get_historical_snapshot(org_id, snapshot_date=date_value)


@router.get("/{org_id}/role-seats/{role_seat_id}/succession")
def get_role_seat_succession_route(
    org_id: str,
    role_seat_id: str,
    project_id: str = Query(..., min_length=1),
    current_user: dict[str, Any] = Depends(require_permission("projects.read")),
):
    _require_org_lane(current_user)
    _require_org_project_access(org_id, project_id, current_user)
    return {"organization_id": org_id, "role_seat_id": role_seat_id, "items": get_role_seat_succession(org_id, role_seat_id)}


@router.get("/{org_id}/viewer/succession-timeline")
def get_succession_timeline_route(
    org_id: str,
    project_id: str = Query(..., min_length=1),
    current_user: dict[str, Any] = Depends(require_permission("projects.read")),
):
    _require_org_lane(current_user)
    _require_org_project_access(org_id, project_id, current_user)
    return {"organization_id": org_id, "items": get_succession_timeline(org_id)}


@router.get("/{org_id}/viewer/officer-wall")
def get_officer_wall_route(
    org_id: str,
    project_id: str = Query(..., min_length=1),
    current_user: dict[str, Any] = Depends(require_permission("projects.read")),
):
    _require_org_lane(current_user)
    _require_org_project_access(org_id, project_id, current_user)
    return {"organization_id": org_id, "items": get_officer_wall(org_id)}


@router.get("/{org_id}/exports/command-roster")
def get_command_roster_export(
    org_id: str,
    project_id: str = Query(..., min_length=1),
    format: str = Query("json", pattern="^(json|csv)$"),
    current_user: dict[str, Any] = Depends(require_permission("projects.read")),
):
    _require_org_lane(current_user)
    _require_org_project_access(org_id, project_id, current_user)
    rows = export_command_roster(org_id)
    _audit(current_user, "organization.command_roster.export", "organization", org_id, details={"organization_id": org_id, "project_id": project_id, "format": format})
    if format == "json":
        return {"organization_id": org_id, "items": rows}
    output = StringIO()
    fields = ["organization_name", "node", "role_seat", "person", "title_rank", "start_date", "status"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return Response(content=output.getvalue(), media_type="text/csv")


@router.post("/{org_id}/admin-seats/invite", status_code=status.HTTP_201_CREATED)
def post_admin_seat_invite(
    org_id: str,
    payload: AdminSeatInvitePayload,
    current_user: dict[str, Any] = Depends(require_permission("uploads.write")),
):
    _require_org_lane(current_user)
    _require_org_project_access(org_id, payload.project_id, current_user)
    item = create_admin_invite(org_id, payload.model_dump(), actor_user_id=_actor_user_id(current_user))
    _audit(current_user, "organization.admin_seat.invite", "organization_admin_invite", f"{org_id}:{payload.project_id}:{payload.email}:{payload.role}", details={"organization_id": org_id, "project_id": payload.project_id})
    return item


@router.post("/{org_id}/notes", status_code=status.HTTP_201_CREATED)
def post_organization_note(
    org_id: str,
    payload: OrganizationNotePayload,
    current_user: dict[str, Any] = Depends(require_permission("uploads.write")),
):
    _require_org_lane(current_user)
    _require_org_project_access(org_id, payload.project_id, current_user)
    item = create_organization_note(org_id, payload.model_dump(), actor_user_id=_actor_user_id(current_user))
    _audit(current_user, "organization.note.create", "organization_note", str(item.get("created_at")), details={"organization_id": org_id, "project_id": payload.project_id, "visibility": payload.visibility, "sensitive": payload.visibility == "internal"})
    return item


@router.post("/{org_id}/white-glove-review/request", status_code=status.HTTP_201_CREATED)
def post_white_glove_review_request(
    org_id: str,
    payload: WhiteGloveRequestPayload,
    current_user: dict[str, Any] = Depends(require_permission("uploads.write")),
):
    _require_org_lane(current_user)
    _require_org_project_access(org_id, payload.project_id, current_user)
    item = create_white_glove_request(org_id, payload.model_dump(), actor_user_id=_actor_user_id(current_user))
    _audit(current_user, "organization.white_glove.request", "organization_white_glove_request", f"{org_id}:{payload.project_id}", details={"organization_id": org_id, "project_id": payload.project_id, "status": item.get("status")})
    return item
