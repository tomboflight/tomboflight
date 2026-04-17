from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.database import get_database
from app.dependencies.auth import require_permission
from app.schemas.verification_record import (
    VerificationRecordCreate,
    VerificationRecordResponse,
    build_verification_record_document,
    build_verification_record_response,
    normalize_verification_status,
)
from app.services.verification_record_service import (
    create_verification_record,
    list_verification_records,
)

router = APIRouter(prefix="/verification-records", tags=["Verification Records"])


class MemberVerificationActionPayload(BaseModel):
    verification_type: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Examples: government_id, birth_certificate, marriage_certificate, adoption_record, founder_review",
    )
    verification_method: str = Field(
        default="admin_review",
        max_length=100,
        description="How the verification decision was made.",
    )
    review_notes: str = Field(
        default="",
        max_length=4000,
        description="Internal admin notes for the verification decision.",
    )
    evidence_summary: str = Field(
        default="",
        max_length=4000,
        description="Short summary of the evidence reviewed.",
    )
    evidence_files: list[str] = Field(
        default_factory=list,
        description="Temporary evidence references or file paths until upload flow is live.",
    )


class MemberVerificationClearPayload(BaseModel):
    review_notes: str = Field(default="", max_length=4000)


def _normalize_value(value: Any) -> str:
    return str(value or "").strip()


def _normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        normalized = _normalize_value(value)
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped


def _review_actor(current_user: dict[str, Any]) -> str:
    return (
        _normalize_email(current_user.get("email"))
        or _normalize_value(current_user.get("full_name"))
        or _normalize_value(current_user.get("name"))
        or _normalize_value(current_user.get("id"))
        or "admin"
    )


def _member_display_name(member: dict[str, Any]) -> str:
    first_name = _normalize_value(member.get("first_name"))
    last_name = _normalize_value(member.get("last_name"))
    return f"{first_name} {last_name}".strip() or "Unknown Member"


def _serialize_member(member: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(member.get("_id")),
        "family_id": member.get("family_id"),
        "first_name": member.get("first_name"),
        "last_name": member.get("last_name"),
        "display_name": _member_display_name(member),
        "birth_year": member.get("birth_year"),
        "generation": member.get("generation"),
        "bio": member.get("bio"),
        "is_verified": bool(member.get("is_verified", False)),
        "verification_status": member.get("verification_status"),
        "verification_method": member.get("verification_method"),
        "verified_by": member.get("verified_by"),
        "verified_at": member.get("verified_at"),
        "verification_notes": member.get("verification_notes"),
    }


def _require_member(member_id: str) -> tuple[Any, dict[str, Any]]:
    try:
        db = get_database()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail="Database is not connected.",
        ) from exc

    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    if not ObjectId.is_valid(member_id):
        raise HTTPException(status_code=400, detail="Invalid member id.")

    member = db["family_members"].find_one({"_id": ObjectId(member_id)})
    if not member:
        raise HTTPException(status_code=404, detail="Family member not found.")

    return db, member


def _matching_evidence_upload_ids(
    *,
    db: Any,
    member: dict[str, Any],
    verification_type: str,
    evidence_files: list[str],
) -> list[str]:
    family_id = _normalize_value(member.get("family_id"))
    member_id = str(member.get("_id"))
    upload_ids: list[str] = []

    explicit_ids = [
        ObjectId(value)
        for value in _dedupe_strings(evidence_files)
        if ObjectId.is_valid(value)
    ]
    if explicit_ids:
        explicit_records = db["uploaded_files"].find(
            {
                "_id": {"$in": explicit_ids},
                "family_id": family_id,
                "member_id": member_id,
                "category": "verification_evidence",
            }
        )
        upload_ids.extend(str(record.get("_id")) for record in explicit_records)

    if verification_type:
        matching_records = (
            db["uploaded_files"]
            .find(
                {
                    "family_id": family_id,
                    "member_id": member_id,
                    "category": "verification_evidence",
                    "verification_type": verification_type,
                }
            )
            .sort("created_at", -1)
        )
        upload_ids.extend(str(record.get("_id")) for record in matching_records)

    return _dedupe_strings(upload_ids)


def _insert_verification_record(
    *,
    db: Any,
    member: dict[str, Any],
    status_value: str,
    verification_type: str,
    verification_method: str,
    review_notes: str,
    evidence_summary: str,
    evidence_files: list[str],
    reviewed_by: str,
) -> dict[str, Any]:
    now_iso = datetime.now(UTC).isoformat()
    normalized_status = normalize_verification_status(status_value)
    normalized_evidence_files = _dedupe_strings(evidence_files)
    evidence_upload_ids = _matching_evidence_upload_ids(
        db=db,
        member=member,
        verification_type=verification_type,
        evidence_files=normalized_evidence_files,
    )

    record = build_verification_record_document(
        {
            "family_id": _normalize_value(member.get("family_id")),
            "member_id": str(member.get("_id")),
            "person_id": str(member.get("_id")),
            "full_name": _member_display_name(member),
            "verification_type": verification_type,
            "verification_method": verification_method,
            "verification_status": normalized_status,
            "review_notes": review_notes,
            "evidence_summary": evidence_summary,
            "evidence_files": normalized_evidence_files,
            "evidence_upload_ids": evidence_upload_ids,
            "reviewed_by": reviewed_by,
            "reviewed_at": now_iso,
            "created_at": now_iso,
            "updated_at": now_iso,
        },
        now_iso=now_iso,
    )
    record.update(
        {
            # Keep the legacy field used by certificate/chamber summaries.
            "status": normalized_status,
        }
    )

    result = db["verification_records"].insert_one(record)
    record["_id"] = result.inserted_id
    return record


def _update_member_verification_state(
    *,
    db: Any,
    member_id: str,
    status_value: str,
    is_verified: bool,
    verification_method: str,
    review_notes: str,
    reviewed_by: str,
    now_iso: str,
) -> dict[str, Any]:
    normalized_status = normalize_verification_status(status_value)

    db["family_members"].update_one(
        {"_id": ObjectId(member_id)},
        {
            "$set": {
                "is_verified": is_verified,
                "verification_status": normalized_status,
                "verification_method": verification_method,
                "verified_by": reviewed_by,
                "verified_at": now_iso,
                "verification_notes": review_notes,
                "updated_at": now_iso,
                "updated_by": reviewed_by,
            }
        },
    )

    updated_member = db["family_members"].find_one({"_id": ObjectId(member_id)})
    if not updated_member:
        raise HTTPException(status_code=404, detail="Family member not found.")
    return updated_member


@router.get("/", response_model=list[VerificationRecordResponse])
def get_verification_records(
    current_user: dict[str, Any] = Depends(require_permission("verification.review")),
):
    records = list_verification_records()
    return [build_verification_record_response(record) for record in records]


@router.get("/member/{member_id}", response_model=list[VerificationRecordResponse])
def get_verification_records_for_member(
    member_id: str,
    current_user: dict[str, Any] = Depends(require_permission("verification.review")),
):
    db, member = _require_member(member_id)

    records = list(
        db["verification_records"]
        .find({"member_id": str(member.get("_id"))})
        .sort("created_at", -1)
    )
    return [build_verification_record_response(record) for record in records]


@router.post("/", response_model=VerificationRecordResponse)
def create_verification_record_route(
    payload: VerificationRecordCreate,
    current_user: dict[str, Any] = Depends(require_permission("verification.review")),
):
    record = create_verification_record(payload)
    return build_verification_record_response(record)


@router.post("/member/{member_id}/verify")
def verify_member_route(
    member_id: str,
    payload: MemberVerificationActionPayload,
    current_user: dict[str, Any] = Depends(require_permission("verification.review")),
):
    db, _member = _require_member(member_id)
    reviewed_by = _review_actor(current_user)
    now_iso = datetime.now(UTC).isoformat()

    updated_member = _update_member_verification_state(
        db=db,
        member_id=member_id,
        status_value="verified",
        is_verified=True,
        verification_method=payload.verification_method,
        review_notes=payload.review_notes,
        reviewed_by=reviewed_by,
        now_iso=now_iso,
    )

    record = _insert_verification_record(
        db=db,
        member=updated_member,
        status_value="verified",
        verification_type=payload.verification_type,
        verification_method=payload.verification_method,
        review_notes=payload.review_notes,
        evidence_summary=payload.evidence_summary,
        evidence_files=payload.evidence_files,
        reviewed_by=reviewed_by,
    )

    return {
        "message": "Member verified successfully.",
        "member": _serialize_member(updated_member),
        "verification_record": build_verification_record_response(record),
    }


@router.post("/member/{member_id}/reject")
def reject_member_verification_route(
    member_id: str,
    payload: MemberVerificationActionPayload,
    current_user: dict[str, Any] = Depends(require_permission("verification.review")),
):
    db, _member = _require_member(member_id)
    reviewed_by = _review_actor(current_user)
    now_iso = datetime.now(UTC).isoformat()

    updated_member = _update_member_verification_state(
        db=db,
        member_id=member_id,
        status_value="rejected",
        is_verified=False,
        verification_method=payload.verification_method,
        review_notes=payload.review_notes,
        reviewed_by=reviewed_by,
        now_iso=now_iso,
    )

    record = _insert_verification_record(
        db=db,
        member=updated_member,
        status_value="rejected",
        verification_type=payload.verification_type,
        verification_method=payload.verification_method,
        review_notes=payload.review_notes,
        evidence_summary=payload.evidence_summary,
        evidence_files=payload.evidence_files,
        reviewed_by=reviewed_by,
    )

    return {
        "message": "Member verification rejected.",
        "member": _serialize_member(updated_member),
        "verification_record": build_verification_record_response(record),
    }


@router.post("/member/{member_id}/pending")
def mark_member_verification_pending_route(
    member_id: str,
    payload: MemberVerificationActionPayload,
    current_user: dict[str, Any] = Depends(require_permission("verification.review")),
):
    db, _member = _require_member(member_id)
    reviewed_by = _review_actor(current_user)
    now_iso = datetime.now(UTC).isoformat()

    updated_member = _update_member_verification_state(
        db=db,
        member_id=member_id,
        status_value="pending",
        is_verified=False,
        verification_method=payload.verification_method,
        review_notes=payload.review_notes,
        reviewed_by=reviewed_by,
        now_iso=now_iso,
    )

    record = _insert_verification_record(
        db=db,
        member=updated_member,
        status_value="pending",
        verification_type=payload.verification_type,
        verification_method=payload.verification_method,
        review_notes=payload.review_notes,
        evidence_summary=payload.evidence_summary,
        evidence_files=payload.evidence_files,
        reviewed_by=reviewed_by,
    )

    return {
        "message": "Member marked as pending verification.",
        "member": _serialize_member(updated_member),
        "verification_record": build_verification_record_response(record),
    }


@router.post("/member/{member_id}/clear")
def clear_member_verification_route(
    member_id: str,
    payload: MemberVerificationClearPayload,
    current_user: dict[str, Any] = Depends(require_permission("verification.review")),
):
    db, _member = _require_member(member_id)
    reviewed_by = _review_actor(current_user)
    now_iso = datetime.now(UTC).isoformat()

    updated_member = _update_member_verification_state(
        db=db,
        member_id=member_id,
        status_value="unverified",
        is_verified=False,
        verification_method="",
        review_notes=payload.review_notes,
        reviewed_by=reviewed_by,
        now_iso=now_iso,
    )

    record = _insert_verification_record(
        db=db,
        member=updated_member,
        status_value="unverified",
        verification_type="clear_verification",
        verification_method="admin_reset",
        review_notes=payload.review_notes,
        evidence_summary="",
        evidence_files=[],
        reviewed_by=reviewed_by,
    )

    return {
        "message": "Member verification cleared.",
        "member": _serialize_member(updated_member),
        "verification_record": build_verification_record_response(record),
    }
