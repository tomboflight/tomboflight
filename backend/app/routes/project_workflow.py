"""Project workflow transition endpoint.

Exposes the existing transition_project() domain function as an
authenticated admin HTTP route.  No mint, certificate, delivery, Stripe,
or email side effects are triggered by a workflow state change.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.database import get_database
from app.dependencies.auth import (
    require_permission,
    transition_project,
    WORKFLOW_ALLOWED_TRANSITIONS,
)

router = APIRouter(prefix="/admin", tags=["Project Workflow"])

# States that are valid targets for the production workflow path.
# This is a subset of all allowed transitions: only forward-progress and
# rework transitions relevant to post-build_ready production are accepted
# through this endpoint.  Pre-build states (draft, purchased, build_ready)
# are managed by the intake pipeline.
PRODUCTION_FORWARD_STATES: frozenset[str] = frozenset(
    {"in_production", "qa_review", "client_review", "delivered"}
)
PRODUCTION_REWORK_STATES: frozenset[str] = frozenset(
    {"in_production", "archived"}
)
# All states this endpoint is permitted to target.
ENDPOINT_ALLOWED_TARGETS: frozenset[str] = (
    PRODUCTION_FORWARD_STATES | PRODUCTION_REWORK_STATES
)


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


class ProjectTransitionPayload(BaseModel):
    to_state: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description=(
            "Target workflow state. Valid production targets: "
            "in_production, qa_review, client_review, delivered, archived."
        ),
    )
    reason: str = Field(
        default="",
        max_length=500,
        description="Human-readable reason for the transition.",
    )
    notes: str = Field(
        default="",
        max_length=2000,
        description="Optional operator notes attached to the transition event.",
    )


class ProjectTransitionResponse(BaseModel):
    project_id: str
    previous_state: str
    current_state: str
    phase: str
    idempotent: bool = False
    message: str = ""


@router.post(
    "/projects/{project_id}/transition",
    response_model=ProjectTransitionResponse,
    status_code=status.HTTP_200_OK,
    summary="Transition a project through its production workflow states",
    description=(
        "Moves a project from its current workflow state to the requested "
        "target state using the established state-machine rules.  Requires "
        "project.workflow.transition permission.  "
        "No mint, certificate, delivery, Stripe, or email side effects are "
        "triggered by this endpoint.  "
        "If the project is already in the requested state, returns a no-op "
        "success with idempotent=true."
    ),
)
def transition_project_route(
    project_id: str,
    payload: ProjectTransitionPayload,
    current_admin: dict[str, Any] = Depends(
        require_permission("project.workflow.transition")
    ),
) -> ProjectTransitionResponse:
    db = get_database()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not connected.",
        )

    from bson import ObjectId

    if not ObjectId.is_valid(project_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project id.",
        )

    project = db["projects"].find_one({"_id": ObjectId(project_id)})
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    target_state = _normalize(payload.to_state)

    # Validate the target is within the states this endpoint manages.
    if target_state not in ENDPOINT_ALLOWED_TARGETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"'{target_state}' is not a valid production workflow target. "
                f"Allowed targets: {sorted(ENDPOINT_ALLOWED_TARGETS)}."
            ),
        )

    current_state = _normalize(project.get("status"))

    # Idempotent: already in the requested state.
    if current_state == target_state:
        return ProjectTransitionResponse(
            project_id=project_id,
            previous_state=current_state,
            current_state=current_state,
            phase=_normalize(project.get("phase")),
            idempotent=True,
            message=f"Project is already in state '{target_state}'. No change made.",
        )

    # Validate the transition is permitted by the state machine.
    allowed = WORKFLOW_ALLOWED_TRANSITIONS.get(current_state, set())
    if target_state not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Transition from '{current_state}' to '{target_state}' is not "
                f"permitted. Allowed transitions from '{current_state}': "
                f"{sorted(allowed) or 'none'}."
            ),
        )

    # Delegate to the fully-implemented domain function which performs its
    # own permission check, state-machine re-validation, audit log write, and
    # workflow event creation.  No mint, certificate, delivery, Stripe, or
    # email calls are made inside transition_project().
    updated_project = transition_project(
        project_id=project_id,
        to_state=target_state,
        actor=current_admin,
    )

    return ProjectTransitionResponse(
        project_id=project_id,
        previous_state=current_state,
        current_state=_normalize(updated_project.get("status")),
        phase=_normalize(updated_project.get("phase")),
        idempotent=False,
        message=(
            f"Project transitioned from '{current_state}' to '{target_state}'."
            + (f" Reason: {payload.reason}" if payload.reason else "")
        ),
    )
