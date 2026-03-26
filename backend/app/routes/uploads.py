from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from bson import ObjectId
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.config import settings
from app.database import get_database
from app.dependencies.auth import get_current_user
from app.services.upload_service import (
    serialize_upload_record,
    store_member_photo_upload,
    store_verification_evidence_upload,
)

router = APIRouter(prefix="/uploads", tags=["Uploads"])

INTERNAL_ADMIN_KEYS = {
    "admin",
    "super_admin",
    "root_admin",
    "platform_admin",
    "operations_admin",
    "finance_admin",
    "marketing_admin",
    "executive_technology",
    "operations",
    "finance",
    "marketing",
}

PHOTO_ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}
PHOTO_ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}
PHOTO_MAX_BYTES = 10 * 1024 * 1024

EVIDENCE_ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}
EVIDENCE_ALLOWED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}
EVIDENCE_MAX_BYTES = 20 * 1024 * 1024

ALLOWED_VERIFICATION_TYPES = {
    "government_id",
    "birth_certificate",
    "marriage_certificate",
    "adoption_record",
    "death_certificate",
    "obituary",
    "supporting_family_record",
}
ALLOWED_EVIDENCE_KINDS = {
    "government_id",
    "birth_certificate",
    "marriage_certificate",
    "adoption_record",
    "death_certificate",
    "obituary",
    "supporting_family_record",
}
ALLOWED_QUERY_CATEGORIES = {
    "member_photo",
    "verification_evidence",
}


def _normalize_value(value: Any) -> str:
    return str(value or "").strip()


def _normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


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
    return _normalize_email(raw_email)


def _current_user_display_name(user: dict[str, Any]) -> str:
    raw_name = user.get("full_name") or user.get("name") or ""
    return _normalize_value(raw_name)


def _actor_label(user: dict[str, Any]) -> str:
    return (
        _normalize_email(user.get("email"))
        or _normalize_value(user.get("full_name"))
        or _normalize_value(user.get("name"))
        or _normalize_value(user.get("id"))
        or "system"
    )


def _is_admin(user: dict[str, Any]) -> bool:
    values = {
        _normalize_value(user.get("role")).lower(),
        _normalize_value(user.get("access_tier")).lower(),
        _normalize_value(user.get("department_role")).lower(),
    }
    return any(value in INTERNAL_ADMIN_KEYS for value in values if value)


def _family_is_visible_to_user(
    family: dict[str, Any],
    current_user_id: str,
    current_user_email: str,
    current_user_name: str,
) -> bool:
    owner_user_id = _normalize_value(family.get("owner_user_id"))
    owner_email = _normalize_email(family.get("owner_email"))

    shared_with_user_ids = [
        _normalize_value(value)
        for value in (family.get("shared_with_user_ids") or [])
        if value is not None
    ]
    shared_with_emails = [
        _normalize_email(value)
        for value in (family.get("shared_with_emails") or [])
        if value is not None
    ]

    if owner_user_id and owner_user_id == current_user_id:
        return True

    if owner_email and owner_email == current_user_email:
        return True

    if current_user_id in shared_with_user_ids:
        return True

    if current_user_email in shared_with_emails:
        return True

    if not owner_user_id and not owner_email:
        created_by = _normalize_value(family.get("created_by"))
        if created_by and (
            created_by == current_user_name or created_by.lower() == current_user_email
        ):
            return True

    return False


def _require_family_access_by_family_id(
    family_id: str,
    db: Any,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    if not family_id:
        raise HTTPException(status_code=400, detail="family_id is required.")

    if not ObjectId.is_valid(family_id):
        raise HTTPException(status_code=400, detail="Invalid family id.")

    family = db["families"].find_one({"_id": ObjectId(family_id)})
    if not family:
        raise HTTPException(status_code=404, detail="Family not found.")

    if _is_admin(current_user):
        return family

    current_user_id = _current_user_id(current_user)
    current_user_email = _current_user_email(current_user)
    current_user_name = _current_user_display_name(current_user)

    if not _family_is_visible_to_user(
        family=family,
        current_user_id=current_user_id,
        current_user_email=current_user_email,
        current_user_name=current_user_name,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this family.",
        )

    return family


def _require_member_access(
    member_id: str,
    db: Any,
    current_user: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not ObjectId.is_valid(member_id):
        raise HTTPException(status_code=400, detail="Invalid member id.")

    member = db["family_members"].find_one({"_id": ObjectId(member_id)})
    if not member:
        raise HTTPException(status_code=404, detail="Family member not found.")

    family_id = _normalize_value(member.get("family_id"))
    family = _require_family_access_by_family_id(family_id, db, current_user)
    return member, family


def _require_upload_access(
    upload_id: str,
    db: Any,
    current_user: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not ObjectId.is_valid(upload_id):
        raise HTTPException(status_code=400, detail="Invalid upload id.")

    upload_record = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)})
    if not upload_record:
        raise HTTPException(status_code=404, detail="Upload not found.")

    family_id = _normalize_value(upload_record.get("family_id"))
    family = _require_family_access_by_family_id(family_id, db, current_user)
    return upload_record, family


def _public_upload_record(record: dict[str, Any]) -> dict[str, Any]:
    serialized = serialize_upload_record(record)
    serialized.pop("relative_path", None)
    serialized.pop("absolute_path", None)
    serialized.pop("storage_path", None)
    return serialized


def _serialize_uploads(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_public_upload_record(record) for record in records]


def _absolute_upload_path(relative_path: str) -> Path:
    root = Path(settings.upload_root_path).resolve()
    candidate = (root / relative_path).resolve()

    if not str(candidate).startswith(str(root)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resolved upload path is invalid.",
        )

    return candidate


def _file_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def _upload_size_bytes(upload: UploadFile) -> int:
    file_obj = upload.file
    current_position = file_obj.tell()
    file_obj.seek(0, 2)
    size = file_obj.tell()
    file_obj.seek(current_position)
    return int(size)


def _validate_category_filter(category: Optional[str]) -> Optional[str]:
    if category is None:
        return None

    normalized = _normalize_value(category)
    if not normalized:
        return None

    if normalized not in ALLOWED_QUERY_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail="Invalid upload category filter.",
        )

    return normalized


def _validate_upload_file(
    upload: UploadFile,
    *,
    allowed_content_types: set[str],
    allowed_extensions: set[str],
    max_bytes: int,
    label: str,
) -> None:
    if upload is None:
        raise HTTPException(status_code=400, detail=f"{label} file is required.")

    filename = _normalize_value(upload.filename)
    if not filename:
        raise HTTPException(status_code=400, detail=f"{label} filename is required.")

    if len(filename) > 255:
        raise HTTPException(status_code=400, detail=f"{label} filename is too long.")

    extension = _file_extension(filename)
    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {label} file extension.",
        )

    content_type = _normalize_value(upload.content_type).lower()
    if content_type not in allowed_content_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {label} content type.",
        )

    size_bytes = _upload_size_bytes(upload)
    if size_bytes <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"{label} file is empty.",
        )

    if size_bytes > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"{label} file exceeds the maximum allowed size.",
        )

    upload.file.seek(0)


@router.post("/member-photo")
async def upload_member_photo(
    family_id: str = Form(...),
    member_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    _validate_upload_file(
        file,
        allowed_content_types=PHOTO_ALLOWED_CONTENT_TYPES,
        allowed_extensions=PHOTO_ALLOWED_EXTENSIONS,
        max_bytes=PHOTO_MAX_BYTES,
        label="member photo",
    )

    member, _family = _require_member_access(member_id, db, current_user)
    actual_family_id = _normalize_value(member.get("family_id"))

    if _normalize_value(family_id) != actual_family_id:
        raise HTTPException(
            status_code=400,
            detail="family_id does not match the selected member.",
        )

    upload_record = await store_member_photo_upload(
        db=db,
        family_id=actual_family_id,
        member_id=member_id,
        upload=file,
        uploaded_by=_actor_label(current_user),
        uploaded_by_user_id=_current_user_id(current_user),
    )

    return {
        "message": "Member photo uploaded successfully.",
        "upload": _public_upload_record(upload_record),
        "member_id": member_id,
        "family_id": actual_family_id,
    }


@router.post("/verification-evidence")
async def upload_verification_evidence(
    family_id: str = Form(...),
    member_id: str = Form(...),
    verification_type: str = Form(...),
    evidence_kind: str = Form("supporting_family_record"),
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    normalized_verification_type = _normalize_value(verification_type)
    normalized_evidence_kind = _normalize_value(evidence_kind)

    if normalized_verification_type not in ALLOWED_VERIFICATION_TYPES:
        raise HTTPException(status_code=400, detail="Invalid verification type.")

    if normalized_evidence_kind not in ALLOWED_EVIDENCE_KINDS:
        raise HTTPException(status_code=400, detail="Invalid evidence kind.")

    _validate_upload_file(
        file,
        allowed_content_types=EVIDENCE_ALLOWED_CONTENT_TYPES,
        allowed_extensions=EVIDENCE_ALLOWED_EXTENSIONS,
        max_bytes=EVIDENCE_MAX_BYTES,
        label="verification evidence",
    )

    member, _family = _require_member_access(member_id, db, current_user)
    actual_family_id = _normalize_value(member.get("family_id"))

    if _normalize_value(family_id) != actual_family_id:
        raise HTTPException(
            status_code=400,
            detail="family_id does not match the selected member.",
        )

    upload_record = await store_verification_evidence_upload(
        db=db,
        family_id=actual_family_id,
        member_id=member_id,
        verification_type=normalized_verification_type,
        evidence_kind=normalized_evidence_kind,
        upload=file,
        uploaded_by=_actor_label(current_user),
        uploaded_by_user_id=_current_user_id(current_user),
    )

    return {
        "message": "Verification evidence uploaded successfully.",
        "upload": _public_upload_record(upload_record),
        "member_id": member_id,
        "family_id": actual_family_id,
    }


@router.get("/member/{member_id}")
def list_member_uploads(
    member_id: str,
    category: Optional[str] = Query(default=None),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    member, _family = _require_member_access(member_id, db, current_user)

    normalized_category = _validate_category_filter(category)

    query: dict[str, Any] = {"member_id": str(member.get("_id"))}
    if normalized_category:
        query["category"] = normalized_category

    records = list(db["uploaded_files"].find(query).sort("created_at", -1))
    return {
        "member_id": str(member.get("_id")),
        "count": len(records),
        "uploads": _serialize_uploads(records),
    }


@router.get("/family/{family_id}")
def list_family_uploads(
    family_id: str,
    category: Optional[str] = Query(default=None),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    _require_family_access_by_family_id(family_id, db, current_user)
    normalized_category = _validate_category_filter(category)

    query: dict[str, Any] = {"family_id": family_id}
    if normalized_category:
        query["category"] = normalized_category

    records = list(db["uploaded_files"].find(query).sort("created_at", -1))
    return {
        "family_id": family_id,
        "count": len(records),
        "uploads": _serialize_uploads(records),
    }


@router.get("/{upload_id}/download")
def download_upload(
    upload_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    upload_record, _family = _require_upload_access(upload_id, db, current_user)

    relative_path = _normalize_value(upload_record.get("relative_path"))
    if not relative_path:
        raise HTTPException(status_code=404, detail="Upload path missing.")

    absolute_path = _absolute_upload_path(relative_path)
    if not absolute_path.exists():
        raise HTTPException(status_code=404, detail="Upload file not found on disk.")

    response = FileResponse(
        path=absolute_path,
        media_type=upload_record.get("content_type") or "application/octet-stream",
        filename=upload_record.get("original_filename") or absolute_path.name,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@router.delete("/{upload_id}")
def delete_upload(
    upload_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    upload_record, _family = _require_upload_access(upload_id, db, current_user)

    relative_path = _normalize_value(upload_record.get("relative_path"))
    if relative_path:
        absolute_path = _absolute_upload_path(relative_path)
        if absolute_path.exists():
            absolute_path.unlink()

    db["uploaded_files"].delete_one({"_id": ObjectId(upload_id)})

    if _normalize_value(upload_record.get("category")) == "member_photo":
        member_id = _normalize_value(upload_record.get("member_id"))
        if ObjectId.is_valid(member_id):
            db["family_members"].update_one(
                {
                    "_id": ObjectId(member_id),
                    "photo_upload_id": upload_id,
                },
                {
                    "$set": {
                        "photo_upload_id": "",
                        "photo_path": "",
                        "photo_original_filename": "",
                        "photo_content_type": "",
                        "photo_size_bytes": 0,
                        "updated_by": _actor_label(current_user),
                        "updated_by_user_id": _current_user_id(current_user),
                    }
                },
            )

    return {
        "status": "deleted",
        "upload_id": upload_id,
    }