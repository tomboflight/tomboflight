from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException, UploadFile, status

from app.config import settings

CHUNK_SIZE = 1024 * 1024

IMAGE_CONTENT_TYPES = set(settings.upload_image_content_types_list)
DOCUMENT_CONTENT_TYPES = set(settings.upload_document_content_types_list)
EVIDENCE_CONTENT_TYPES = IMAGE_CONTENT_TYPES | DOCUMENT_CONTENT_TYPES

EXTENSION_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}


def _safe_path_token(value: Any) -> str:
    raw = str(value or "").strip()
    cleaned = "".join(ch for ch in raw if ch.isalnum() or ch in {"-", "_"})
    return cleaned or "unknown"


def _safe_original_filename(filename: str | None) -> str:
    name = Path(str(filename or "upload")).name
    name = "".join(ch for ch in name if ch.isprintable() and ch not in {"/", "\\"})
    name = name.strip() or "upload"

    if len(name) > 255:
        suffix = Path(name).suffix[:10]
        stem = Path(name).stem[:200]
        name = f"{stem}{suffix}"

    return name


def _extension_for_upload(filename: str | None, content_type: str) -> str:
    mapped = EXTENSION_BY_CONTENT_TYPE.get(content_type.lower())
    if mapped:
        return mapped

    suffix = Path(str(filename or "")).suffix.lower()
    if suffix and 1 <= len(suffix) <= 10:
        return suffix

    return ".bin"


def _upload_root() -> Path:
    root = Path(settings.upload_root_path)
    root.mkdir(parents=True, exist_ok=True)
    return root


async def _save_upload_to_disk(
    upload: UploadFile,
    destination: Path,
    max_bytes: int,
) -> int:
    size_bytes = 0
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        with destination.open("wb") as file_handle:
            while True:
                chunk = await upload.read(CHUNK_SIZE)
                if not chunk:
                    break

                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Upload exceeded max allowed size of {max_bytes} bytes.",
                    )

                file_handle.write(chunk)
    except Exception:
        if destination.exists():
            destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    return size_bytes


def serialize_upload_record(record: dict[str, Any]) -> dict[str, Any]:
    record_id = str(record.get("_id") or record.get("id") or "")
    return {
        "id": record_id,
        "family_id": record.get("family_id"),
        "member_id": record.get("member_id"),
        "category": record.get("category"),
        "evidence_kind": record.get("evidence_kind"),
        "verification_type": record.get("verification_type"),
        "original_filename": record.get("original_filename"),
        "stored_filename": record.get("stored_filename"),
        "content_type": record.get("content_type"),
        "size_bytes": record.get("size_bytes"),
        "uploaded_by": record.get("uploaded_by"),
        "uploaded_by_user_id": record.get("uploaded_by_user_id"),
        "created_at": record.get("created_at"),
        "download_path": f"/uploads/{record_id}/download" if record_id else "",
    }


async def store_member_photo_upload(
    *,
    db: Any,
    family_id: str,
    member_id: str,
    upload: UploadFile,
    uploaded_by: str,
    uploaded_by_user_id: str = "",
) -> dict[str, Any]:
    content_type = str(upload.content_type or "").strip().lower()
    if content_type not in IMAGE_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported member photo type. Allowed: JPEG, PNG, WEBP.",
        )

    original_filename = _safe_original_filename(upload.filename)
    extension = _extension_for_upload(original_filename, content_type)

    family_token = _safe_path_token(family_id)
    member_token = _safe_path_token(member_id)
    stored_filename = f"{uuid4().hex}{extension}"

    relative_path = Path("member_photos") / family_token / member_token / stored_filename
    absolute_path = _upload_root() / relative_path

    size_bytes = await _save_upload_to_disk(
        upload=upload,
        destination=absolute_path,
        max_bytes=settings.upload_max_image_bytes,
    )

    now_iso = datetime.now(UTC).isoformat()

    upload_record = {
        "family_id": family_id,
        "member_id": member_id,
        "category": "member_photo",
        "evidence_kind": "",
        "verification_type": "",
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "relative_path": str(relative_path).replace("\\", "/"),
        "content_type": content_type,
        "size_bytes": size_bytes,
        "uploaded_by": uploaded_by,
        "uploaded_by_user_id": uploaded_by_user_id,
        "storage_provider": "local_disk",
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    result = db["uploaded_files"].insert_one(upload_record)
    upload_record["_id"] = result.inserted_id
    upload_id = str(result.inserted_id)

    db["family_members"].update_one(
        {"_id": ObjectId(member_id)},
        {
            "$set": {
                "photo_upload_id": upload_id,
                "photo_path": upload_record["relative_path"],
                "photo_original_filename": original_filename,
                "photo_content_type": content_type,
                "photo_size_bytes": size_bytes,
                "updated_at": now_iso,
                "updated_by": uploaded_by,
                "updated_by_user_id": uploaded_by_user_id,
            }
        },
    )

    return serialize_upload_record(upload_record)


async def store_verification_evidence_upload(
    *,
    db: Any,
    family_id: str,
    member_id: str,
    verification_type: str,
    evidence_kind: str,
    upload: UploadFile,
    uploaded_by: str,
    uploaded_by_user_id: str = "",
) -> dict[str, Any]:
    content_type = str(upload.content_type or "").strip().lower()
    if content_type not in EVIDENCE_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported evidence file type. Allowed: PDF, JPEG, PNG, WEBP.",
        )

    original_filename = _safe_original_filename(upload.filename)
    extension = _extension_for_upload(original_filename, content_type)

    family_token = _safe_path_token(family_id)
    member_token = _safe_path_token(member_id)
    evidence_token = _safe_path_token(evidence_kind or "supporting_record")
    stored_filename = f"{uuid4().hex}{extension}"

    relative_path = (
        Path("verification_evidence")
        / family_token
        / member_token
        / evidence_token
        / stored_filename
    )
    absolute_path = _upload_root() / relative_path

    size_bytes = await _save_upload_to_disk(
        upload=upload,
        destination=absolute_path,
        max_bytes=settings.upload_max_document_bytes,
    )

    now_iso = datetime.now(UTC).isoformat()

    upload_record = {
        "family_id": family_id,
        "member_id": member_id,
        "category": "verification_evidence",
        "evidence_kind": evidence_kind,
        "verification_type": verification_type,
        "original_filename": original_filename,
        "stored_filename": stored_filename,
        "relative_path": str(relative_path).replace("\\", "/"),
        "content_type": content_type,
        "size_bytes": size_bytes,
        "uploaded_by": uploaded_by,
        "uploaded_by_user_id": uploaded_by_user_id,
        "storage_provider": "local_disk",
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    result = db["uploaded_files"].insert_one(upload_record)
    upload_record["_id"] = result.inserted_id

    return serialize_upload_record(upload_record)