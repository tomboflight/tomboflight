"""Customer-facing client review routes.

GET  /projects/{project_id}/client-review           — load review context
POST /projects/{project_id}/client-review/approve   — record approval
POST /projects/{project_id}/client-review/request-revision — record revision request

No mint, certificate, delivery, Stripe, or email side effects are triggered
by any route in this module.  Larry Robinson's canonical mint is never touched.
"""

from __future__ import annotations

from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.database import get_database
from app.dependencies.auth import get_current_user, has_internal_admin_access
from app.services.client_review_service import (
    create_approval,
    create_revision_request,
    get_latest_review,
)
from app.services.project_membership_service import get_project_access_snapshot
from app.services.project_entitlement_service import get_project_entitlement

router = APIRouter(prefix="/projects", tags=["Client Review"])

CLIENT_REVIEW_STATE = "client_review"


def _normalize(value: Any) -> str:
    return str(value or "").strip()


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


def _assert_project_access(
    project: dict[str, Any],
    current_user: dict[str, Any],
) -> None:
    """Raise 403 if the current user cannot access this project."""
    if has_internal_admin_access(current_user):
        return

    user_id = _current_user_id(current_user)
    user_email = _current_user_email(current_user)

    snapshot = get_project_access_snapshot(
        project,
        user_id=user_id,
        email=user_email,
    )
    if not snapshot.get("accessible"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this project.",
        )


def _load_project(project_id: str) -> dict[str, Any]:
    db = get_database()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not connected.",
        )
    if not ObjectId.is_valid(project_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project id.",
        )
    project = db["projects"].find_one({"_id": ObjectId(project_id)})
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return project


def _assert_client_review_state(project: dict[str, Any]) -> None:
    current_state = _normalize(project.get("status"))
    if current_state != CLIENT_REVIEW_STATE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This project is not ready for customer review. "
                f"Current state: '{current_state}'. "
                f"Review actions are only available when the project is in "
                f"'{CLIENT_REVIEW_STATE}'."
            ),
        )


def _build_review_context(
    project: dict[str, Any],
    current_user: dict[str, Any],
    latest_review: dict[str, Any] | None,
) -> dict[str, Any]:
    project_id = str(project.get("_id") or "")
    entitlement = get_project_entitlement(project_id) or {}
    current_state = _normalize(project.get("status"))
    is_in_review = current_state == CLIENT_REVIEW_STATE

    db = get_database()
    family = None
    household = None
    if db is not None:
        family_id = _normalize(project.get("family_id"))
        household_id = _normalize(project.get("household_id"))
        if family_id and ObjectId.is_valid(family_id):
            family = db["families"].find_one({"_id": ObjectId(family_id)}) or None
        if household_id and ObjectId.is_valid(household_id):
            household = db["households"].find_one({"_id": ObjectId(household_id)}) or None

    # Fetch approved public-facing uploads only — never expose vault/private media.
    approved_uploads: list[dict[str, Any]] = []
    if db is not None:
        raw_uploads = list(
            db["uploaded_files"]
            .find(
                {
                    "project_id": project_id,
                    "customer_visible": True,
                    "approved_for_cinematic": True,
                    "quarantined": {"$ne": True},
                    "category": {"$in": ["member_photo"]},
                }
            )
            .limit(50)
        )
        for u in raw_uploads:
            approved_uploads.append(
                {
                    "upload_id": str(u.get("_id") or ""),
                    "original_filename": _normalize(u.get("original_filename")),
                    "category": _normalize(u.get("category")),
                    "member_id": _normalize(u.get("member_id")),
                }
            )

    return {
        "project_id": project_id,
        "project_name": _normalize(
            project.get("project_name") or project.get("name")
        ),
        "package_code": _normalize(
            project.get("package_code") or entitlement.get("package_code")
        ),
        "package_name": _normalize(
            project.get("package_name") or entitlement.get("package_name")
        ),
        "current_state": current_state,
        "phase": _normalize(project.get("phase")),
        "ready_for_review": is_in_review,
        "family_name": _normalize((family or {}).get("family_name")),
        "household_name": _normalize((household or {}).get("household_name")),
        "approved_public_uploads": approved_uploads,
        "latest_review": latest_review,
        # Private vault media is deliberately excluded from this response.
        "vault_media_excluded": True,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "/{project_id}/client-review",
    summary="Load client review context for a project",
)
def get_client_review(
    project_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the review context for the authenticated customer.

    Includes project metadata, approved public-facing uploads, and the latest
    review record.  Private vault media is never included.
    """
    project = _load_project(project_id)
    _assert_project_access(project, current_user)
    latest = get_latest_review(project_id)
    return _build_review_context(project, current_user, latest)


class ApprovePayload(BaseModel):
    version: str = Field(default="1", max_length=50)
    comments: str = Field(default="", max_length=2000)
    public_safe_consent: bool = Field(
        ...,
        description=(
            "Customer explicitly confirms that the reviewed content is "
            "approved for public-facing viewer and collectible presentation. "
            "This does NOT authorize a new mint or remint."
        ),
    )


@router.post(
    "/{project_id}/client-review/approve",
    status_code=status.HTTP_201_CREATED,
    summary="Record customer approval of the production version",
)
def approve_client_review(
    project_id: str,
    payload: ApprovePayload,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Record a customer approval decision.

    Only permitted when the project is in client_review state.
    Does NOT mint, remint, issue a certificate, mark delivered, or change billing.
    For Larry Robinson: public_safe_consent is approval for viewer content and
    delivery presentation only — his existing canonical mint is unchanged.
    """
    project = _load_project(project_id)
    _assert_project_access(project, current_user)
    _assert_client_review_state(project)

    record = create_approval(
        project_id=project_id,
        user_id=_current_user_id(current_user),
        user_email=_current_user_email(current_user),
        version=payload.version,
        comments=payload.comments,
        public_safe_consent=payload.public_safe_consent,
    )
    return {
        "message": "Approval recorded. The production team will proceed to certificate and delivery.",
        "review": record,
        # Explicit confirmation that no mint action was taken.
        "mint_action": "none",
        "certificate_action": "none",
        "delivery_action": "none",
    }


class RevisionRequestPayload(BaseModel):
    version: str = Field(default="1", max_length=50)
    comments: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Required description of what needs to be changed.",
    )


@router.post(
    "/{project_id}/client-review/request-revision",
    status_code=status.HTTP_201_CREATED,
    summary="Record a customer revision request",
)
def request_revision(
    project_id: str,
    payload: RevisionRequestPayload,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Record a customer request for production revisions.

    Only permitted when the project is in client_review state.
    Does NOT automatically return the project to in_production — a production
    team operator must read this record and take action.
    Does NOT change billing, mint records, or certificates.
    """
    project = _load_project(project_id)
    _assert_project_access(project, current_user)
    _assert_client_review_state(project)

    try:
        record = create_revision_request(
            project_id=project_id,
            user_id=_current_user_id(current_user),
            user_email=_current_user_email(current_user),
            version=payload.version,
            comments=payload.comments,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "message": "Revision request recorded. The production team will review your comments and contact you.",
        "review": record,
        "mint_action": "none",
        "certificate_action": "none",
        "delivery_action": "none",
    }
