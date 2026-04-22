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
            "status": "unavailable",
            "route_service": "No dedicated organization support-record verification route/service yet.",
            "permission_gate": "N/A",
            "entitlement_gate": "N/A",
            "audit_behavior": "N/A",
            "duplicate_prevention_behavior": "N/A",
            "error_state": "Show explicit unavailable state until verification workflow route is implemented.",
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
            "status": "unavailable",
            "route_service": "Viewer mode exists but historical_date_view is currently available=false.",
            "permission_gate": "N/A",
            "entitlement_gate": "N/A",
            "audit_behavior": "N/A",
            "duplicate_prevention_behavior": "N/A",
            "error_state": "Show unavailable badge in UI; do not render as live action.",
        },
        {
            "button": "View Succession Timeline",
            "status": "unavailable",
            "route_service": "Viewer mode exists but succession_timeline is currently available=false.",
            "permission_gate": "N/A",
            "entitlement_gate": "N/A",
            "audit_behavior": "N/A",
            "duplicate_prevention_behavior": "N/A",
            "error_state": "Show unavailable badge in UI; do not render as live action.",
        },
        {
            "button": "View Officer Wall",
            "status": "unavailable",
            "route_service": "Viewer mode exists but officer_wall is currently available=false.",
            "permission_gate": "N/A",
            "entitlement_gate": "N/A",
            "audit_behavior": "N/A",
            "duplicate_prevention_behavior": "N/A",
            "error_state": "Show unavailable badge in UI; do not render as live action.",
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
            "status": "unavailable",
            "route_service": "No organization roster export route/service yet.",
            "permission_gate": "N/A",
            "entitlement_gate": "N/A",
            "audit_behavior": "N/A",
            "duplicate_prevention_behavior": "N/A",
            "error_state": "Show unavailable badge and block action.",
        },
        {
            "button": "Invite Admin Seat",
            "status": "unavailable",
            "route_service": "No organization-specific admin-seat invitation route/service yet.",
            "permission_gate": "N/A",
            "entitlement_gate": "N/A",
            "audit_behavior": "N/A",
            "duplicate_prevention_behavior": "N/A",
            "error_state": "Show unavailable badge and block action.",
        },
        {
            "button": "Add Ops / Support Note",
            "status": "unavailable",
            "route_service": "No dedicated ops/support note endpoint for command structure network yet.",
            "permission_gate": "N/A",
            "entitlement_gate": "N/A",
            "audit_behavior": "N/A",
            "duplicate_prevention_behavior": "N/A",
            "error_state": "Show unavailable badge and block action.",
        },
        {
            "button": "Request White-Glove Review",
            "status": "unavailable",
            "route_service": "No command-structure white-glove review request route/service yet.",
            "permission_gate": "N/A",
            "entitlement_gate": "N/A",
            "audit_behavior": "N/A",
            "duplicate_prevention_behavior": "N/A",
            "error_state": "Show unavailable badge and block action.",
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
