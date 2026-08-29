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
PRIVATE_VOICE_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/ogg",
}
PRIVATE_VIDEO_CONTENT_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/ogg",
}
PRIVATE_MEDIA_CONTENT_TYPES = PRIVATE_VOICE_CONTENT_TYPES | PRIVATE_VIDEO_CONTENT_TYPES
VAULT_PHOTO_CONTENT_TYPES = IMAGE_CONTENT_TYPES
VAULT_DOCUMENT_CONTENT_TYPES = EVIDENCE_CONTENT_TYPES

EXTENSION_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/ogg": ".ogv",
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


def _safe_version(value: Any) -> int:
    try:
        return max(int(value or 1), 1)
    except (TypeError, ValueError):
        return 1


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
        "project_id": record.get("project_id"),
        "family_id": record.get("family_id"),
        "member_id": record.get("member_id"),
        "category": record.get("category"),
        "evidence_kind": record.get("evidence_kind"),
        "verification_type": record.get("verification_type"),
        "original_filename": record.get("original_filename"),
        "stored_filename": record.get("stored_filename"),
        # Internal callers need this to run malware scanning. Public routes remove it.
        "relative_path": record.get("relative_path"),
        "content_type": record.get("content_type"),
        "size_bytes": record.get("size_bytes"),
        "uploaded_by": record.get("uploaded_by"),
        "uploaded_by_user_id": record.get("uploaded_by_user_id"),
        "vault_scope": record.get("vault_scope"),
        "visibility_scope": record.get("visibility_scope"),
        "privacy_scope": record.get("privacy_scope") or record.get("visibility_scope"),
        "privacy_classification": record.get("privacy_classification"),
        "relationship_scope": record.get("relationship_scope"),
        "branch_id": record.get("branch_id"),
        "person_ids": list(record.get("person_ids") or []),
        "asset_type": record.get("asset_type") or record.get("category"),
        "verification_status": record.get("verification_status") or "pending",
        "consent_status": record.get("consent_status") or "pending",
        "consent_attested": bool(record.get("consent_attested")),
        "authority_attested": bool(record.get("authority_attested")),
        "consent_attested_at": record.get("consent_attested_at"),
        "authority_attested_at": record.get("authority_attested_at"),
        "approved_for_cinematic": bool(record.get("approved_for_cinematic")),
        "approved_by": record.get("approved_by"),
        "master_review_status": record.get("master_review_status") or "pending",
        "master_reviewed_at": record.get("master_reviewed_at"),
        "master_review_notes": record.get("master_review_notes") or "",
        "verified_by": record.get("verified_by"),
        "verified_at": record.get("verified_at"),
        "verification_review_notes": record.get("verification_review_notes") or "",
        "share_with_linked_families": bool(record.get("share_with_linked_families")),
        "customer_visible": bool(record.get("customer_visible", True)),
        "internal_only": bool(record.get("internal_only")),
        "scan_status": record.get("scan_status"),
        "scan_detail": record.get("scan_detail"),
        "quarantined": bool(record.get("quarantined")),
        "quarantine_reason": record.get("quarantine_reason"),
        "account_access_enabled": (
            record.get("account_access_enabled") is not False
            and not bool(record.get("owner_account_deleted"))
        ),
        "vault_item_id": record.get("vault_item_id"),
        "version": _safe_version(record.get("version")),
        "version_group_id": record.get("version_group_id") or record_id,
        "root_upload_id": record.get("version_group_id") or record_id,
        "replaces_upload_id": record.get("replaces_upload_id") or None,
        "superseded_by_upload_id": record.get("superseded_by_upload_id") or None,
        "pending_replacement_upload_id": record.get("pending_replacement_upload_id") or None,
        "replacement_status": record.get("replacement_status") or "current",
        "is_current_version": bool(record.get("is_current_version", True)),
        "release_state": record.get("release_state") or "released",
        "reveal_at": record.get("reveal_at"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "download_path": f"/uploads/{record_id}/download" if record_id else "",
    }


def _upload_lifecycle_fields(
    *,
    account_access_enabled: bool,
    vault_item_id: str,
    version: int,
    version_group_id: str,
    replaces_upload_id: str,
    idempotency_key_hash: str,
    idempotency_fingerprint: str,
) -> dict[str, Any]:
    normalized_version = _safe_version(version)
    normalized_replaces = str(replaces_upload_id or "").strip()
    return {
        "account_access_enabled": bool(account_access_enabled),
        "owner_account_deleted": False,
        "vault_item_id": str(vault_item_id or "").strip() or None,
        "version": normalized_version,
        "version_group_id": str(version_group_id or "").strip(),
        "replaces_upload_id": normalized_replaces or None,
        "superseded_by_upload_id": None,
        "pending_replacement_upload_id": None,
        "replacement_status": "pending" if normalized_replaces else "current",
        "is_current_version": not bool(normalized_replaces),
        "idempotency_key_hash": str(idempotency_key_hash or "").strip() or None,
        "idempotency_fingerprint": str(idempotency_fingerprint or "").strip() or None,
    }


def _insert_upload_record(
    *,
    db: Any,
    upload_record: dict[str, Any],
    absolute_path: Path,
) -> str:
    """Insert a staged upload and compensate if Mongo persistence fails."""

    try:
        result = db["uploaded_files"].insert_one(upload_record)
    except Exception:
        absolute_path.unlink(missing_ok=True)
        raise

    upload_record["_id"] = result.inserted_id
    upload_id = str(result.inserted_id)
    if not str(upload_record.get("version_group_id") or "").strip():
        upload_record["version_group_id"] = upload_id
        try:
            db["uploaded_files"].update_one(
                {"_id": result.inserted_id},
                {"$set": {"version_group_id": upload_id}},
            )
        except Exception:
            # The inserted row is still authoritative and serialization falls
            # back to its own id. A reconciliation/index pass can backfill it.
            pass
    return upload_id


async def store_member_photo_upload(
    *,
    db: Any,
    project_id: str,
    family_id: str,
    member_id: str,
    upload: UploadFile,
    uploaded_by: str,
    uploaded_by_user_id: str = "",
    consent_attested: bool = False,
    authority_attested: bool = False,
    vault_item_id: str = "",
    version: int = 1,
    version_group_id: str = "",
    replaces_upload_id: str = "",
    idempotency_key_hash: str = "",
    idempotency_fingerprint: str = "",
) -> dict[str, Any]:
    if not consent_attested or not authority_attested:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portrait consent and upload authority must both be confirmed.",
        )
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
        "project_id": project_id,
        "family_id": family_id,
        "member_id": member_id,
        "category": "member_photo",
        "internal_only": False,
        "customer_visible": True,
        "vault_scope": "family_shared",
        "visibility_scope": "household_private",
        "privacy_scope": "household_private",
        "privacy_classification": "household_private",
        "relationship_scope": "household_member",
        "branch_id": "",
        "person_ids": [member_id] if member_id else [],
        "asset_type": "portrait",
        "verification_status": "pending",
        "consent_status": "pending",
        "consent_attested": True,
        "authority_attested": True,
        "consent_attested_at": now_iso,
        "consent_attested_by_user_id": uploaded_by_user_id,
        "authority_attested_at": now_iso,
        "authority_attested_by_user_id": uploaded_by_user_id,
        "approved_for_cinematic": False,
        "approved_by": None,
        "master_review_status": "pending",
        "master_reviewed_at": None,
        "master_review_notes": "",
        "share_with_linked_families": False,
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
        "scan_status": "pending",
        "scan_detail": "",
        "quarantined": False,
        "quarantine_reason": "",
        "created_at": now_iso,
        "updated_at": now_iso,
        **_upload_lifecycle_fields(
            account_access_enabled=True,
            vault_item_id=vault_item_id,
            version=version,
            version_group_id=version_group_id,
            replaces_upload_id=replaces_upload_id,
            idempotency_key_hash=idempotency_key_hash,
            idempotency_fingerprint=idempotency_fingerprint,
        ),
    }

    upload_id = _insert_upload_record(
        db=db,
        upload_record=upload_record,
        absolute_path=absolute_path,
    )

    db["family_members"].update_one(
        {"_id": ObjectId(member_id)},
        {
            "$set": {
                "pending_photo_upload_id": upload_id,
                "photo_submission_status": "pending_scan",
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
    project_id: str,
    family_id: str,
    member_id: str,
    verification_type: str,
    evidence_kind: str,
    upload: UploadFile,
    uploaded_by: str,
    uploaded_by_user_id: str = "",
    vault_item_id: str = "",
    version: int = 1,
    version_group_id: str = "",
    replaces_upload_id: str = "",
    idempotency_key_hash: str = "",
    idempotency_fingerprint: str = "",
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
        "project_id": project_id,
        "family_id": family_id,
        "member_id": member_id,
        "category": "verification_evidence",
        "internal_only": False,
        "customer_visible": False,
        "vault_scope": "personal",
        "visibility_scope": "private_to_owner",
        "privacy_scope": "private_to_owner",
        "privacy_classification": "private_to_owner",
        "relationship_scope": "self",
        "branch_id": "",
        "person_ids": [member_id],
        "asset_type": "verification_document",
        "verification_status": "pending",
        "consent_status": "pending",
        "approved_for_cinematic": False,
        "approved_by": None,
        "share_with_linked_families": False,
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
        "scan_status": "pending",
        "scan_detail": "",
        "quarantined": False,
        "quarantine_reason": "",
        "created_at": now_iso,
        "updated_at": now_iso,
        **_upload_lifecycle_fields(
            account_access_enabled=True,
            vault_item_id=vault_item_id,
            version=version,
            version_group_id=version_group_id,
            replaces_upload_id=replaces_upload_id,
            idempotency_key_hash=idempotency_key_hash,
            idempotency_fingerprint=idempotency_fingerprint,
        ),
    }

    _insert_upload_record(
        db=db,
        upload_record=upload_record,
        absolute_path=absolute_path,
    )

    return serialize_upload_record(upload_record)


async def store_private_media_upload(
    *,
    db: Any,
    project_id: str,
    family_id: str,
    member_id: str,
    asset_type: str,
    privacy_scope: str,
    upload: UploadFile,
    uploaded_by: str,
    uploaded_by_user_id: str = "",
    vault_scope: str = "personal",
    consent_attested: bool = False,
    authority_attested: bool = False,
    vault_item_id: str = "",
    version: int = 1,
    version_group_id: str = "",
    replaces_upload_id: str = "",
    idempotency_key_hash: str = "",
    idempotency_fingerprint: str = "",
    release_state: str = "released",
    reveal_at: str | None = None,
    share_with_linked_families: bool = False,
) -> dict[str, Any]:
    normalized_asset_type = str(asset_type or "").strip().lower()
    normalized_privacy_scope = str(privacy_scope or "").strip().lower() or "private_to_owner"
    content_type = str(upload.content_type or "").strip().lower()
    allowed_content_types = set(PRIVATE_MEDIA_CONTENT_TYPES)
    if normalized_asset_type == "vault_photo":
        allowed_content_types = set(VAULT_PHOTO_CONTENT_TYPES)
    elif normalized_asset_type == "vault_document":
        allowed_content_types = set(VAULT_DOCUMENT_CONTENT_TYPES)

    if content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported private vault file type.",
        )

    if consent_attested is not True or authority_attested is not True:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vault consent and upload authority must both be confirmed.",
        )

    if normalized_asset_type == "private_voice_message" and content_type not in PRIVATE_VOICE_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported voice media type.",
        )

    if normalized_asset_type == "private_video_message" and content_type not in PRIVATE_VIDEO_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported video media type.",
        )

    original_filename = _safe_original_filename(upload.filename)
    extension = _extension_for_upload(original_filename, content_type)
    family_token = _safe_path_token(family_id)
    member_token = _safe_path_token(member_id)
    asset_token = _safe_path_token(normalized_asset_type or "private_media")
    stored_filename = f"{uuid4().hex}{extension}"
    relative_path = Path("private_media") / family_token / member_token / asset_token / stored_filename
    absolute_path = _upload_root() / relative_path

    max_bytes = (
        settings.upload_max_image_bytes
        if normalized_asset_type == "vault_photo"
        else settings.upload_max_document_bytes
    )
    size_bytes = await _save_upload_to_disk(
        upload=upload,
        destination=absolute_path,
        max_bytes=max_bytes,
    )

    now_iso = datetime.now(UTC).isoformat()
    customer_visible = normalized_privacy_scope != "private_to_owner"
    upload_record = {
        "project_id": project_id,
        "family_id": family_id,
        "member_id": member_id,
        "category": "private_media",
        "internal_only": False,
        "customer_visible": customer_visible,
        "vault_scope": str(vault_scope or "personal").strip().lower() or "personal",
        "visibility_scope": normalized_privacy_scope,
        "privacy_scope": normalized_privacy_scope,
        "privacy_classification": normalized_privacy_scope,
        "relationship_scope": "self",
        "branch_id": "",
        "person_ids": [member_id] if member_id else [],
        "asset_type": normalized_asset_type or "private_media",
        "verification_status": "pending",
        "consent_status": "pending",
        "consent_attested": True,
        "authority_attested": True,
        "consent_attested_at": now_iso,
        "consent_attested_by_user_id": uploaded_by_user_id,
        "authority_attested_at": now_iso,
        "authority_attested_by_user_id": uploaded_by_user_id,
        "approved_for_cinematic": False,
        "approved_by": None,
        "share_with_linked_families": bool(share_with_linked_families),
        "release_state": str(release_state or "released").strip().lower() or "released",
        "reveal_at": str(reveal_at or "").strip() or None,
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
        "scan_status": "pending",
        "scan_detail": "",
        "quarantined": False,
        "quarantine_reason": "",
        "created_at": now_iso,
        "updated_at": now_iso,
        **_upload_lifecycle_fields(
            account_access_enabled=True,
            vault_item_id=vault_item_id,
            version=version,
            version_group_id=version_group_id,
            replaces_upload_id=replaces_upload_id,
            idempotency_key_hash=idempotency_key_hash,
            idempotency_fingerprint=idempotency_fingerprint,
        ),
    }
    _insert_upload_record(
        db=db,
        upload_record=upload_record,
        absolute_path=absolute_path,
    )
    return serialize_upload_record(upload_record)
