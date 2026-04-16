from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


DEFAULT_VERIFICATION_METHOD = "admin_review"
DEFAULT_VERIFICATION_STATUS = "pending"
DEFAULT_VERIFICATION_TYPE = "unspecified"


def _normalize_string(value: Any) -> str:
    return str(value or "").strip()


def _first_string(*values: Any) -> str:
    for value in values:
        normalized = _normalize_string(value)
        if normalized:
            return normalized
    return ""


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        raw_items = value.replace("\n", ",").split(",")
    elif isinstance(value, list):
        raw_items = value
    elif isinstance(value, tuple) or isinstance(value, set):
        raw_items = list(value)
    else:
        raw_items = [value]

    normalized: list[str] = []
    for item in raw_items:
        item_value = _normalize_string(item)
        if item_value and item_value not in normalized:
            normalized.append(item_value)
    return normalized


def _serialize_datetime(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return _normalize_string(value)


def normalize_verification_status(value: Any) -> str:
    status = _normalize_string(value).lower()
    if not status:
        return DEFAULT_VERIFICATION_STATUS

    aliases = {
        "approved": "verified",
        "passed": "verified",
        "pass": "verified",
        "complete": "verified",
        "completed": "verified",
        "denied": "rejected",
        "failed": "rejected",
        "fail": "rejected",
        "reset": "unverified",
        "clear": "unverified",
        "cleared": "unverified",
        "unverify": "unverified",
    }
    return aliases.get(status, status)


def normalize_verification_record_data(data: dict[str, Any]) -> dict[str, Any]:
    verification_type = _first_string(
        data.get("verification_type"),
        data.get("record_type"),
        data.get("evidence_kind"),
        DEFAULT_VERIFICATION_TYPE,
    )
    verification_method = _first_string(
        data.get("verification_method"),
        data.get("method"),
        DEFAULT_VERIFICATION_METHOD,
    )
    verification_status = normalize_verification_status(
        _first_string(
            data.get("verification_status"),
            data.get("status"),
            data.get("review_status"),
            DEFAULT_VERIFICATION_STATUS,
        )
    )
    reviewed_by = _first_string(
        data.get("reviewed_by"),
        data.get("verified_by"),
        data.get("approved_by"),
    )
    reviewed_at = _serialize_datetime(
        data.get("reviewed_at")
        or data.get("verified_at")
        or data.get("approved_at")
    )
    review_notes = _first_string(data.get("review_notes"), data.get("notes"))
    document_url = _first_string(
        data.get("document_url"),
        data.get("evidence_url"),
        data.get("file_url"),
    )

    evidence_files = _normalize_list(data.get("evidence_files"))
    if not document_url and evidence_files:
        document_url = evidence_files[0]
    if document_url and document_url not in evidence_files:
        evidence_files.append(document_url)

    created_at = _serialize_datetime(data.get("created_at"))
    updated_at = _serialize_datetime(data.get("updated_at")) or created_at

    return {
        "id": _normalize_string(data.get("_id") or data.get("id")),
        "family_id": _normalize_string(data.get("family_id")) or None,
        "member_id": _normalize_string(data.get("member_id")) or None,
        "person_id": _normalize_string(data.get("person_id")) or None,
        "relationship_id": _normalize_string(data.get("relationship_id")) or None,
        "canonical_person_id": _normalize_string(data.get("canonical_person_id")) or None,
        "full_name": _normalize_string(data.get("full_name")),
        "verification_type": verification_type,
        "record_type": verification_type,
        "document_url": document_url,
        "verification_method": verification_method,
        "verification_status": verification_status,
        "status": verification_status,
        "reviewed_by": reviewed_by or None,
        "reviewed_at": reviewed_at or None,
        "verified_by": reviewed_by or None,
        "review_notes": review_notes or None,
        "notes": review_notes or None,
        "evidence_summary": _normalize_string(data.get("evidence_summary")),
        "evidence_files": evidence_files,
        "evidence_upload_ids": _normalize_list(data.get("evidence_upload_ids")),
        "created_at": created_at or datetime.now(UTC).isoformat(),
        "updated_at": updated_at or created_at or datetime.now(UTC).isoformat(),
    }


def build_verification_record_document(
    data: dict[str, Any],
    *,
    now_iso: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_verification_record_data(data)
    timestamp = now_iso or datetime.now(UTC).isoformat()

    document = dict(data)
    document.update(
        {
            "family_id": normalized["family_id"],
            "member_id": normalized["member_id"],
            "person_id": normalized["person_id"],
            "relationship_id": normalized["relationship_id"],
            "canonical_person_id": normalized["canonical_person_id"],
            "full_name": normalized["full_name"],
            "verification_type": normalized["verification_type"],
            "verification_method": normalized["verification_method"],
            "verification_status": normalized["verification_status"],
            "reviewed_by": normalized["reviewed_by"],
            "reviewed_at": normalized["reviewed_at"],
            "review_notes": normalized["review_notes"],
            "evidence_summary": normalized["evidence_summary"],
            "evidence_files": normalized["evidence_files"],
            "evidence_upload_ids": normalized["evidence_upload_ids"],
            "created_at": normalized["created_at"] or timestamp,
            "updated_at": normalized["updated_at"] or timestamp,
            # Compatibility aliases for existing clients and legacy records.
            "record_type": normalized["record_type"],
            "document_url": normalized["document_url"],
            "status": normalized["status"],
            "verified_by": normalized["verified_by"],
            "notes": normalized["notes"],
        }
    )
    document.pop("id", None)
    return document


class VerificationRecordCreate(BaseModel):
    family_id: str | None = None
    member_id: str | None = None
    person_id: str | None = None
    relationship_id: str | None = None
    canonical_person_id: str | None = None
    full_name: str | None = Field(default=None, max_length=200)
    verification_type: str | None = Field(default=None, max_length=100)
    verification_method: str = Field(default=DEFAULT_VERIFICATION_METHOD, max_length=100)
    verification_status: str = Field(default="pending", min_length=1, max_length=50)
    reviewed_by: str | None = Field(default=None, max_length=200)
    reviewed_at: str | None = None
    review_notes: str | None = Field(default=None, max_length=4000)
    evidence_summary: str = Field(default="", max_length=4000)
    evidence_files: list[str] = Field(default_factory=list)
    evidence_upload_ids: list[str] = Field(default_factory=list)
    record_type: str | None = Field(default=None, max_length=100)
    document_url: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, max_length=50)
    verified_by: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def require_verification_type(self) -> "VerificationRecordCreate":
        if not _first_string(self.verification_type, self.record_type):
            raise ValueError("verification_type or record_type is required.")
        return self


class VerificationRecordResponse(BaseModel):
    id: str
    family_id: str | None = None
    member_id: str | None = None
    person_id: str | None = None
    relationship_id: str | None = None
    canonical_person_id: str | None = None
    full_name: str = ""
    verification_type: str
    verification_method: str
    verification_status: str
    status: str
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    review_notes: str | None = None
    evidence_summary: str = ""
    evidence_files: list[str] = Field(default_factory=list)
    evidence_upload_ids: list[str] = Field(default_factory=list)
    # Legacy aliases kept in the response so old admin/front-end code still works.
    record_type: str
    document_url: str
    verified_by: str | None = None
    notes: str | None = None
    created_at: str
    updated_at: str


def build_verification_record_response(data: dict) -> VerificationRecordResponse:
    return VerificationRecordResponse(**normalize_verification_record_data(data))
