from __future__ import annotations

from datetime import UTC, datetime
import re
import secrets
import shutil
from pathlib import Path
from typing import Any, Literal, Optional

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
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.database import get_database
from app.dependencies.auth import (
    enforce_limit,
    get_current_user,
    has_internal_admin_access,
    require_entitlement,
    require_permission,
)
from app.services.upload_service import (
    serialize_upload_record,
    store_member_photo_upload,
    store_private_media_upload,
    store_verification_evidence_upload,
)
from app.services.r2_storage_service import generate_private_download_url
from app.services.upload_scan_service import scan_uploaded_file
from app.services.audit_log_service import create_audit_log
from app.services.privacy_access_service import (
    can_access_cinematic_asset,
    can_access_privacy_scope,
    normalize_privacy_scope,
)
from app.services.tree_service import list_linked_family_ids
from app.services.workspace_access_service import (
    count_workspace_uploads,
    family_is_visible_to_user,
    require_workspace_capability,
    require_workspace_member_role,
    resolve_workspace_context,
)

router = APIRouter(prefix="/uploads", tags=["Uploads"])

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
PHOTO_MAX_BYTES = settings.upload_max_image_bytes

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
EVIDENCE_MAX_BYTES = settings.upload_max_document_bytes

PRIVATE_MEDIA_ALLOWED_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/ogg",
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/ogg",
}
PRIVATE_MEDIA_ALLOWED_EXTENSIONS = {
    ".mp3",
    ".m4a",
    ".wav",
    ".webm",
    ".ogg",
    ".mp4",
    ".mov",
    ".ogv",
}
PRIVATE_MEDIA_ALLOWED_ASSET_TYPES = {"private_voice_message", "private_video_message"}
PRIVATE_MEDIA_ALLOWED_PRIVACY_SCOPES = {"private_to_owner", "private_to_owner_and_co_owner"}
HOUSEHOLD_VAULT_CAPABILITY = "can_use_household_vault"

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
    "private_media",
}
ALLOWED_VAULT_SCOPE = {"personal", "family_shared"}
ALLOWED_VISIBILITY_SCOPE = {
    "private_to_owner",
    "private_to_owner_and_co_owner",
    "household_private",
    "branch_shared",
    "linked_family_shared",
    "public_memorial",
    "minor_protected",
    "private",
    "family_shared",
    "internal_only",
}
ALLOWED_PRIVACY_CLASSIFICATION = {
    "private_to_owner",
    "private_to_owner_and_co_owner",
    "household_private",
    "branch_shared",
    "linked_family_shared",
    "public_memorial",
    "minor_protected",
    "public",
    "shared",
    "household_only",
    "owner_only",
    "admin_only",
}


class UploadPrivacyUpdatePayload(BaseModel):
    vault_scope: Literal["personal", "family_shared"] | None = None
    visibility_scope: Literal[
        "private_to_owner",
        "private_to_owner_and_co_owner",
        "household_private",
        "branch_shared",
        "linked_family_shared",
        "public_memorial",
        "minor_protected",
    ] | None = None
    customer_visible: bool | None = None
    internal_only: bool | None = None
    share_with_linked_families: bool | None = None
    privacy_notes: str = Field(default="", max_length=500)
    privacy_classification: Literal[
        "private_to_owner",
        "private_to_owner_and_co_owner",
        "household_private",
        "branch_shared",
        "linked_family_shared",
        "public_memorial",
        "minor_protected",
    ] | None = None


class UploadCinematicApprovalPayload(BaseModel):
    approved_for_cinematic: bool = Field(default=True)
    verification_status: str = Field(default="approved", max_length=50)
    consent_status: str = Field(default="approved", max_length=50)


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
    return has_internal_admin_access(user)


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

    if has_internal_admin_access(current_user):
        return family

    current_user_id = _current_user_id(current_user)
    current_user_email = _current_user_email(current_user)
    current_user_name = _current_user_display_name(current_user)

    if not family_is_visible_to_user(
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
    *,
    detail: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not ObjectId.is_valid(upload_id):
        raise HTTPException(status_code=400, detail="Invalid upload id.")

    upload_record = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)})
    if not upload_record:
        raise HTTPException(status_code=404, detail="Upload not found.")

    family_id = _normalize_value(upload_record.get("family_id"))
    project_id = _normalize_value(upload_record.get("project_id"))
    context = require_workspace_capability(
        current_user,
        project_id=project_id,
        family_id=family_id,
        capabilities=("can_upload_portraits", "can_upload_verification_docs"),
        detail=detail,
    )

    if (
        not context.get("is_admin")
        and project_id
        and _normalize_value(context["project"].get("_id")) != project_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Upload does not belong to the current workspace.",
        )

    if not context.get("is_admin"):
        current_user_id = _current_user_id(current_user)
        uploaded_by_user_id = _normalize_value(upload_record.get("uploaded_by_user_id"))
        owns_record = bool(current_user_id and uploaded_by_user_id and current_user_id == uploaded_by_user_id)
        if bool(upload_record.get("internal_only")) and not owns_record:
            try:
                create_audit_log(
                    "private_file_access_denied",
                    current_user_id or None,
                    "upload",
                    upload_id,
                    {"reason": "visibility_policy"},
                )
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This file is not visible to customers.",
            )

        if not bool(upload_record.get("customer_visible")) and not owns_record:
            try:
                create_audit_log(
                    "private_file_access_denied",
                    current_user_id or None,
                    "upload",
                    upload_id,
                    {"reason": "visibility_policy"},
                )
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This file is not visible to customers.",
            )

        classification = _normalize_privacy_classification(
            upload_record.get("privacy_classification"),
            fallback=_classification_from_flags(
                visibility_scope=_normalize_visibility_scope(upload_record.get("visibility_scope"), "private"),
                internal_only=bool(upload_record.get("internal_only")),
                customer_visible=bool(upload_record.get("customer_visible")),
            ),
        )
        if not _can_access_classification(
            classification,
            context=context,
            upload_record=upload_record,
            current_user=current_user,
        ):
            try:
                create_audit_log(
                    "private_file_access_denied",
                    current_user_id or None,
                    "upload",
                    upload_id,
                    {"reason": "privacy_classification", "privacy_classification": classification},
                )
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied for this file privacy classification.",
            )

    return upload_record, context


def _require_upload_management_access(
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
    project_id = _normalize_value(upload_record.get("project_id"))
    context = resolve_workspace_context(
        current_user,
        project_id=project_id,
        family_id=family_id,
    )

    if context.get("is_admin"):
        return upload_record, context

    current_user_id = _current_user_id(current_user)
    uploaded_by_user_id = _normalize_value(upload_record.get("uploaded_by_user_id"))
    member_role = _normalize_value(context.get("member_role"))
    if current_user_id == uploaded_by_user_id:
        return upload_record, context

    if member_role in {"billing_owner", "co_owner", "family_manager"}:
        return upload_record, context

    project_owner_user_id = _normalize_value((context.get("project") or {}).get("owner_user_id"))
    if current_user_id == project_owner_user_id:
        return upload_record, context

    if current_user_id not in {uploaded_by_user_id, project_owner_user_id}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this upload.",
        )

    return upload_record, context


def _public_upload_record(record: dict[str, Any]) -> dict[str, Any]:
    serialized = serialize_upload_record(record)
    serialized.pop("relative_path", None)
    serialized.pop("absolute_path", None)
    serialized.pop("storage_path", None)
    serialized.pop("uploaded_by_user_id", None)
    return serialized


def _serialize_uploads(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_public_upload_record(record) for record in records]


def _display_member_name(member: dict[str, Any] | None) -> str | None:
    if not isinstance(member, dict):
        return None

    first_name = _normalize_value(member.get("first_name"))
    last_name = _normalize_value(member.get("last_name"))
    display_name = f"{first_name} {last_name}".strip()
    return display_name or _normalize_value(member.get("display_name")) or None


def _serialize_admin_upload_review(
    record: dict[str, Any],
    *,
    db: Any,
) -> dict[str, Any]:
    serialized = _public_upload_record(record)

    project_id = _normalize_value(record.get("project_id"))
    family_id = _normalize_value(record.get("family_id"))
    member_id = _normalize_value(record.get("member_id"))

    project = None
    family = None
    member = None

    if ObjectId.is_valid(project_id):
        project = db["projects"].find_one({"_id": ObjectId(project_id)})
    if ObjectId.is_valid(family_id):
        family = db["families"].find_one({"_id": ObjectId(family_id)})
    if ObjectId.is_valid(member_id):
        member = db["family_members"].find_one({"_id": ObjectId(member_id)})

    return {
        **serialized,
        "project_id": project_id or None,
        "project_name": _normalize_value((project or {}).get("project_name") or (project or {}).get("name")) or None,
        "project_owner_email": _normalize_email((project or {}).get("owner_email")) or None,
        "family_id": family_id or None,
        "family_name": _normalize_value((family or {}).get("family_name")) or None,
        "member_id": member_id or None,
        "member_name": _display_member_name(member),
    }


def _absolute_upload_path(relative_path: str) -> Path:
    root = Path(settings.upload_root_path).resolve()
    candidate = (root / relative_path).resolve()

    try:
        candidate.relative_to(root)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resolved upload path is invalid.",
        )

    return candidate


def _quarantine_path_for_upload(relative_path: str) -> Path:
    quarantine_root = Path(settings.upload_quarantine_dir).resolve()
    quarantine_root.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(
        character
        for character in Path(relative_path).name
        if character.isalnum() or character in {"-", "_"}
    ).strip("_")
    safe_name = safe_name or "upload_quarantine_item"
    safe_name = f"{safe_name}-{secrets.token_hex(4)}"
    candidate = (quarantine_root / safe_name).resolve()
    try:
        candidate.relative_to(quarantine_root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Resolved quarantine path is invalid.")
    return candidate


def _scan_and_quarantine_upload(*, db: Any, upload_record: dict[str, Any]) -> dict[str, Any]:
    upload_id = str(upload_record.get("id") or upload_record.get("_id") or "")
    relative_path = _normalize_value(upload_record.get("relative_path"))
    if not upload_id or not relative_path:
        return upload_record
    absolute_path = _absolute_upload_path(relative_path)
    result = scan_uploaded_file(str(absolute_path))
    if result.status in {"infected", "error"}:
        quarantine_path = _quarantine_path_for_upload(relative_path)
        quarantined = False
        quarantine_detail = result.detail[:500] or result.status
        if absolute_path.exists():
            try:
                quarantine_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(absolute_path), str(quarantine_path))
                quarantined = True
            except OSError as exc:
                del exc
                quarantine_detail = f"{quarantine_detail}; move_failed"
        db["uploaded_files"].update_one(
            {"_id": ObjectId(upload_id)},
            {
                "$set": {
                    "scan_status": result.status,
                    "scan_detail": quarantine_detail,
                    "quarantined": quarantined,
                    "quarantine_reason": quarantine_detail,
                    "quarantine_path": str(quarantine_path) if quarantined else "",
                }
            },
        )
    else:
        db["uploaded_files"].update_one(
            {"_id": ObjectId(upload_id)},
            {"$set": {"scan_status": result.status, "scan_detail": result.detail[:500], "quarantined": False}},
        )
    refreshed = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)})
    return refreshed or upload_record


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


def _normalize_vault_scope(value: Any, default: str = "personal") -> str:
    normalized = _normalize_value(value).lower()
    return normalized if normalized in ALLOWED_VAULT_SCOPE else default


def _normalize_visibility_scope(value: Any, default: str = "private") -> str:
    normalized = _normalize_value(value).lower()
    if normalized in ALLOWED_VISIBILITY_SCOPE:
        return normalize_privacy_scope(normalized)
    return normalize_privacy_scope(default)


def _visibility_flags(scope: str) -> dict[str, bool]:
    """Return default privacy flags for a given visibility scope."""
    normalized_scope = _normalize_visibility_scope(scope, default="private_to_owner")
    if normalized_scope == "private_to_owner":
        return {
            "customer_visible": False,
            "internal_only": False,
            "share_with_linked_families": False,
        }
    if normalized_scope == "private_to_owner_and_co_owner":
        return {
            "customer_visible": True,
            "internal_only": False,
            "share_with_linked_families": False,
        }
    if normalized_scope in {"linked_family_shared", "branch_shared", "public_memorial"}:
        return {
            "customer_visible": True,
            "internal_only": False,
            "share_with_linked_families": normalized_scope == "linked_family_shared",
        }
    return {
        "customer_visible": True,
        "internal_only": False,
        "share_with_linked_families": False,
    }


def _classification_from_flags(
    *,
    visibility_scope: str,
    internal_only: bool,
    customer_visible: bool,
) -> str:
    normalized_scope = _normalize_visibility_scope(visibility_scope, "private_to_owner")
    if internal_only:
        return "private_to_owner"
    if normalized_scope in {
        "private_to_owner",
        "private_to_owner_and_co_owner",
        "household_private",
        "branch_shared",
        "linked_family_shared",
        "public_memorial",
        "minor_protected",
    }:
        return normalized_scope
    return "household_private" if customer_visible else "private_to_owner"


def _normalize_privacy_classification(value: Any, *, fallback: str) -> str:
    normalized = normalize_privacy_scope(value)
    if normalized in ALLOWED_PRIVACY_CLASSIFICATION:
        return normalized
    return normalize_privacy_scope(fallback)


def _can_access_classification(
    classification: str,
    *,
    context: dict[str, Any],
    upload_record: dict[str, Any],
    current_user: dict[str, Any],
) -> bool:
    # Workspace admins intentionally bypass classification gating so support/security
    # workflows can still operate across all vault privacy classes.
    if context.get("is_admin"):
        return True
    normalized = _normalize_privacy_classification(classification, fallback="private_to_owner")
    user_id = _current_user_id(current_user)
    uploaded_by_user_id = _normalize_value(upload_record.get("uploaded_by_user_id"))
    return can_access_privacy_scope(
        privacy_scope=normalized,
        member_role=context.get("member_role") or "viewer",
        relationship_scope=context.get("relationship_scope") or "household_member",
        link_status=context.get("link_status") or "active",
        is_owner=bool(user_id and uploaded_by_user_id and user_id == uploaded_by_user_id),
    )


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


def _enforce_allowed_asset_type(
    *,
    context: dict[str, Any],
    asset_type: str,
) -> None:
    if bool(context.get("is_admin")):
        return
    allowed = {
        _normalize_value(value).lower()
        for value in (context.get("resolved_entitlements") or {}).get("allowed_asset_types") or []
        if _normalize_value(value)
    }
    if allowed and _normalize_value(asset_type).lower() not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your active package does not permit this private media type.",
        )


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _enforce_workspace_upload_limit(context: dict[str, Any]) -> None:
    entitlements = context.get("resolved_entitlements") or {}
    max_uploads = _as_int(entitlements.get("max_uploads"), 0)
    if max_uploads <= 0:
        return

    family_id = _normalize_value((context.get("family") or {}).get("_id"))
    project_id = _normalize_value((context.get("project") or {}).get("_id"))
    current_count = count_workspace_uploads(family_id=family_id, project_id=project_id)
    enforce_limit("uploads", current_count + 1, context=context)


def _workspace_storage_used_bytes(*, db: Any, project_id: str, family_id: str) -> int:
    """Return cumulative uploaded size for a project/family, treating missing size as zero."""
    query: dict[str, Any] = {}
    if project_id:
        query["project_id"] = project_id
    elif family_id:
        query["family_id"] = family_id
    else:
        return 0
    pipeline = [
        {"$match": query},
        {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$size_bytes", 0]}}}},
    ]
    results = list(db["uploaded_files"].aggregate(pipeline))
    if not results:
        return 0
    return _as_int(results[0].get("total"), 0)


def _enforce_workspace_storage_limit(
    *,
    context: dict[str, Any],
    db: Any,
    incoming_size_bytes: int,
) -> None:
    family_id = _normalize_value((context.get("family") or {}).get("_id"))
    project_id = _normalize_value((context.get("project") or {}).get("_id"))
    used_bytes = _workspace_storage_used_bytes(
        db=db,
        project_id=project_id,
        family_id=family_id,
    )
    enforce_limit(
        "vault_storage_bytes",
        used_bytes + max(incoming_size_bytes, 0),
        context=context,
    )


def _apply_customer_visibility_filter(
    query: dict[str, Any],
    *,
    is_admin: bool,
    current_user: dict[str, Any],
) -> None:
    if is_admin:
        return

    current_user_id = _current_user_id(current_user)
    query["$or"] = [
        {
            "uploaded_by_user_id": current_user_id,
            "privacy_classification": {"$nin": ["admin_only"]},
        },
        {
            "customer_visible": True,
            "internal_only": {"$ne": True},
            "privacy_classification": {
                "$nin": [
                    "owner_only",
                    "admin_only",
                    "private_to_owner",
                ]
            },
        },
        {"privacy_classification": "public"},
        {"privacy_classification": "public_memorial"},
    ]


@router.get("/admin/review")
def list_admin_uploads(
    category: Optional[str] = Query(default=None),
    project_id: str = Query(default=""),
    family_id: str = Query(default=""),
    member_id: str = Query(default=""),
    search: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: dict[str, Any] = Depends(require_permission("uploads.admin.review")),
):
    del current_user

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    normalized_category = _validate_category_filter(category)
    normalized_project_id = _normalize_value(project_id)
    normalized_family_id = _normalize_value(family_id)
    normalized_member_id = _normalize_value(member_id)
    normalized_search = _normalize_value(search)

    query: dict[str, Any] = {}
    if normalized_category:
        query["category"] = normalized_category
    if normalized_project_id:
        query["project_id"] = normalized_project_id
    if normalized_family_id:
        query["family_id"] = normalized_family_id
    if normalized_member_id:
        query["member_id"] = normalized_member_id
    if normalized_search:
        regex = {"$regex": re.escape(normalized_search), "$options": "i"}
        query["$or"] = [
            {"original_filename": regex},
            {"uploaded_by": regex},
            {"verification_type": regex},
            {"evidence_kind": regex},
            {"project_id": regex},
            {"family_id": regex},
            {"member_id": regex},
        ]

    records = list(
        db["uploaded_files"].find(query).sort("created_at", -1).limit(limit)
    )

    return {
        "count": len(records),
        "items": [
            _serialize_admin_upload_review(record, db=db)
            for record in records
        ],
    }


@router.post("/member-photo")
async def upload_member_photo(
    family_id: str = Form(...),
    member_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    context = require_workspace_capability(
        current_user,
        family_id=family_id,
        member_id=member_id,
        capabilities=("can_upload_portraits",),
        detail="Your active package does not include upload access.",
    )
    require_workspace_member_role(
        context,
        allowed_roles=("billing_owner", "co_owner", "family_manager", "contributor"),
        detail="Your role is read-only for uploads.",
    )

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

    member = context["member"]
    actual_family_id = _normalize_value(member.get("family_id"))

    if _normalize_value(family_id) != actual_family_id:
        raise HTTPException(
            status_code=400,
            detail="family_id does not match the selected member.",
        )

    _enforce_workspace_upload_limit(context)
    _enforce_workspace_storage_limit(
        context=context,
        db=db,
        incoming_size_bytes=_upload_size_bytes(file),
    )

    upload_record = await store_member_photo_upload(
        db=db,
        project_id=_normalize_value(context["project"].get("_id")),
        family_id=actual_family_id,
        member_id=member_id,
        upload=file,
        uploaded_by=_actor_label(current_user),
        uploaded_by_user_id=_current_user_id(current_user),
    )
    upload_record = _scan_and_quarantine_upload(db=db, upload_record=upload_record)

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
    context = require_workspace_capability(
        current_user,
        family_id=family_id,
        member_id=member_id,
        capabilities=("can_upload_verification_docs",),
        detail="Your active package does not include upload access.",
    )
    require_workspace_member_role(
        context,
        allowed_roles=("billing_owner", "co_owner", "family_manager", "contributor"),
        detail="Your role is read-only for uploads.",
    )

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

    member = context["member"]
    actual_family_id = _normalize_value(member.get("family_id"))

    if _normalize_value(family_id) != actual_family_id:
        raise HTTPException(
            status_code=400,
            detail="family_id does not match the selected member.",
        )

    _enforce_workspace_upload_limit(context)
    _enforce_workspace_storage_limit(
        context=context,
        db=db,
        incoming_size_bytes=_upload_size_bytes(file),
    )

    upload_record = await store_verification_evidence_upload(
        db=db,
        project_id=_normalize_value(context["project"].get("_id")),
        family_id=actual_family_id,
        member_id=member_id,
        verification_type=normalized_verification_type,
        evidence_kind=normalized_evidence_kind,
        upload=file,
        uploaded_by=_actor_label(current_user),
        uploaded_by_user_id=_current_user_id(current_user),
    )
    upload_record = _scan_and_quarantine_upload(db=db, upload_record=upload_record)

    return {
        "message": "Verification evidence uploaded successfully.",
        "upload": _public_upload_record(upload_record),
        "member_id": member_id,
        "family_id": actual_family_id,
    }


@router.post("/private-media")
async def upload_private_media(
    family_id: str = Form(...),
    member_id: str = Form(...),
    asset_type: str = Form(...),
    privacy_scope: str = Form("private_to_owner"),
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    context = require_workspace_capability(
        current_user,
        family_id=family_id,
        member_id=member_id,
        capabilities=(HOUSEHOLD_VAULT_CAPABILITY,),
        detail="Your active package does not include private household vault access.",
    )
    require_workspace_member_role(
        context,
        allowed_roles=("billing_owner", "co_owner", "family_manager", "contributor"),
        detail="Your role is read-only for uploads.",
    )

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    normalized_asset_type = _normalize_value(asset_type).lower()
    if normalized_asset_type not in PRIVATE_MEDIA_ALLOWED_ASSET_TYPES:
        raise HTTPException(status_code=400, detail="Invalid private media asset type.")

    normalized_privacy_scope = _normalize_visibility_scope(privacy_scope, "private_to_owner")
    if normalized_privacy_scope not in PRIVATE_MEDIA_ALLOWED_PRIVACY_SCOPES:
        raise HTTPException(status_code=400, detail="Invalid private media privacy scope.")

    _enforce_allowed_asset_type(context=context, asset_type=normalized_asset_type)
    _validate_upload_file(
        file,
        allowed_content_types=PRIVATE_MEDIA_ALLOWED_CONTENT_TYPES,
        allowed_extensions=PRIVATE_MEDIA_ALLOWED_EXTENSIONS,
        max_bytes=EVIDENCE_MAX_BYTES,
        label="private media",
    )

    member = context["member"]
    actual_family_id = _normalize_value(member.get("family_id"))
    if _normalize_value(family_id) != actual_family_id:
        raise HTTPException(status_code=400, detail="family_id does not match the selected member.")

    _enforce_workspace_upload_limit(context)
    _enforce_workspace_storage_limit(
        context=context,
        db=db,
        incoming_size_bytes=_upload_size_bytes(file),
    )

    upload_record = await store_private_media_upload(
        db=db,
        project_id=_normalize_value(context["project"].get("_id")),
        family_id=actual_family_id,
        member_id=member_id,
        asset_type=normalized_asset_type,
        privacy_scope=normalized_privacy_scope,
        upload=file,
        uploaded_by=_actor_label(current_user),
        uploaded_by_user_id=_current_user_id(current_user),
    )
    upload_record = _scan_and_quarantine_upload(db=db, upload_record=upload_record)
    return {
        "message": "Private media uploaded successfully.",
        "upload": _public_upload_record(upload_record),
        "member_id": member_id,
        "family_id": actual_family_id,
    }


@router.get("/member/{member_id}")
def list_member_uploads(
    member_id: str,
    category: Optional[str] = Query(default=None),
    current_user: dict[str, Any] = Depends(
        require_entitlement("can_upload_portraits", allow_internal_admin=True)
    ),
):
    context = require_workspace_capability(
        current_user,
        member_id=member_id,
        capabilities=("can_upload_verification_docs", "can_upload_portraits"),
        detail="Your active package does not include upload access.",
    )

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    member = context["member"]
    family = context["family"]
    project = context["project"]

    normalized_category = _validate_category_filter(category)

    query: dict[str, Any] = {
        "member_id": str(member.get("_id")),
        "family_id": _normalize_value((family or {}).get("_id")),
        "project_id": _normalize_value((project or {}).get("_id")),
    }
    _apply_customer_visibility_filter(
        query,
        is_admin=bool(context.get("is_admin")),
        current_user=current_user,
    )
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
    current_user: dict[str, Any] = Depends(
        require_entitlement("can_upload_portraits", allow_internal_admin=True)
    ),
):
    context = require_workspace_capability(
        current_user,
        family_id=family_id,
        capabilities=("can_upload_verification_docs", "can_upload_portraits"),
        detail="Your active package does not include upload access.",
    )

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    family = context["family"]
    project = context["project"]
    normalized_category = _validate_category_filter(category)

    query: dict[str, Any] = {
        "family_id": _normalize_value((family or {}).get("_id")),
        "project_id": _normalize_value((project or {}).get("_id")),
    }
    _apply_customer_visibility_filter(
        query,
        is_admin=bool(context.get("is_admin")),
        current_user=current_user,
    )
    if normalized_category:
        query["category"] = normalized_category

    records = list(db["uploaded_files"].find(query).sort("created_at", -1))
    return {
        "family_id": _normalize_value((family or {}).get("_id")),
        "count": len(records),
        "uploads": _serialize_uploads(records),
    }


@router.get("/vault/family/{family_id}")
def list_family_vault_items(
    family_id: str,
    include_linked_families: bool = Query(default=False),
    vault_scope: Optional[str] = Query(default=None),
    visibility_scope: Optional[str] = Query(default=None),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    context = require_workspace_capability(
        current_user,
        family_id=family_id,
        capabilities=(HOUSEHOLD_VAULT_CAPABILITY,),
        detail="Your active package does not include private household vault access.",
    )

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    base_family_id = _normalize_value((context.get("family") or {}).get("_id"))
    family_ids = [base_family_id]
    if include_linked_families:
        has_link_capability = bool(context.get("is_admin")) or bool(
            (context.get("resolved_entitlements") or {}).get("can_link_households")
        )
        if not has_link_capability:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your active package does not include linked family vault access.",
            )
        family_ids = list_linked_family_ids(base_family_id)

    query: dict[str, Any] = {
        "family_id": {"$in": [fid for fid in family_ids if fid]},
    }
    normalized_scope = _normalize_vault_scope(vault_scope, default="")
    if normalized_scope:
        query["vault_scope"] = normalized_scope
    normalized_visibility = _normalize_visibility_scope(visibility_scope, default="")
    if normalized_visibility:
        query["visibility_scope"] = normalized_visibility

    current_user_id = _current_user_id(current_user)
    if not context.get("is_admin"):
        query["$or"] = [
            {"uploaded_by_user_id": current_user_id},
            {
                "customer_visible": True,
                "internal_only": {"$ne": True},
                "privacy_classification": {"$nin": ["owner_only", "admin_only"]},
            },
            {"privacy_classification": "public"},
        ]

    records = list(db["uploaded_files"].find(query).sort("created_at", -1))
    return {
        "family_id": base_family_id,
        "linked_family_ids": family_ids,
        "count": len(records),
        "items": _serialize_uploads(records),
    }


@router.patch("/{upload_id}/privacy")
def update_upload_privacy(
    upload_id: str,
    payload: UploadPrivacyUpdatePayload,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    upload_record, context = _require_upload_management_access(
        upload_id,
        db,
        current_user,
    )

    current_scope = _normalize_visibility_scope(upload_record.get("visibility_scope"), "private")
    visibility_scope = (
        _normalize_visibility_scope(payload.visibility_scope, current_scope)
        if payload.visibility_scope is not None
        else current_scope
    )
    flag_defaults = _visibility_flags(visibility_scope)
    customer_visible = flag_defaults["customer_visible"]
    internal_only = flag_defaults["internal_only"]
    share_with_linked = flag_defaults["share_with_linked_families"]

    if payload.customer_visible is not None:
        customer_visible = bool(payload.customer_visible)
    if payload.internal_only is not None:
        internal_only = bool(payload.internal_only)
    if payload.share_with_linked_families is not None:
        share_with_linked = bool(payload.share_with_linked_families)
    if internal_only:
        customer_visible = False
        visibility_scope = "internal_only"

    current_vault_scope = _normalize_vault_scope(upload_record.get("vault_scope"), "personal")
    next_vault_scope = (
        _normalize_vault_scope(payload.vault_scope, current_vault_scope)
        if payload.vault_scope is not None
        else current_vault_scope
    )
    next_classification = _normalize_privacy_classification(
        payload.privacy_classification,
        fallback=_classification_from_flags(
            visibility_scope=visibility_scope,
            internal_only=internal_only,
            customer_visible=customer_visible,
        ),
    )
    if next_classification == "admin_only":
        internal_only = True
        customer_visible = False
        visibility_scope = "internal_only"
    elif next_classification == "owner_only":
        customer_visible = False

    db["uploaded_files"].update_one(
        {"_id": ObjectId(upload_id)},
        {
            "$set": {
                "vault_scope": next_vault_scope,
                "visibility_scope": visibility_scope,
                "customer_visible": customer_visible,
                "internal_only": internal_only,
                "share_with_linked_families": share_with_linked,
                "privacy_notes": _normalize_value(payload.privacy_notes),
                "privacy_classification": next_classification,
            }
        },
    )
    updated = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)}) or upload_record
    return {
        "upload": _public_upload_record(updated),
        "workspace_project_id": _normalize_value((context.get("project") or {}).get("_id")) or None,
    }


@router.post("/{upload_id}/cinematic-approval")
def update_upload_cinematic_approval(
    upload_id: str,
    payload: UploadCinematicApprovalPayload,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    upload_record, context = _require_upload_management_access(upload_id, db, current_user)
    if not context.get("is_admin") and _normalize_value(context.get("member_role")) not in {
        "billing_owner",
        "co_owner",
        "family_manager",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to approve cinematic assets.",
        )
    now = datetime.now(UTC).isoformat()
    db["uploaded_files"].update_one(
        {"_id": ObjectId(upload_id)},
        {
            "$set": {
                "approved_for_cinematic": bool(payload.approved_for_cinematic),
                "approved_by": _actor_label(current_user),
                "approved_by_user_id": _current_user_id(current_user),
                "verification_status": _normalize_value(payload.verification_status).lower() or "approved",
                "consent_status": _normalize_value(payload.consent_status).lower() or "approved",
                "updated_at": now,
            }
        },
    )
    updated = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)}) or upload_record
    return {"upload": _public_upload_record(updated)}


@router.get("/cinematic/family/{family_id}")
def list_cinematic_assets(
    family_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    context = require_workspace_capability(
        current_user,
        family_id=family_id,
        capabilities=("can_upload_verification_docs", "can_upload_portraits"),
        detail="Your active package does not include cinematic asset access.",
    )
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")
    query = {
        "family_id": _normalize_value((context.get("family") or {}).get("_id")),
        "approved_for_cinematic": True,
    }
    records = list(db["uploaded_files"].find(query).sort("created_at", -1))
    user_id = _current_user_id(current_user)
    visible = [
        record
        for record in records
        if can_access_cinematic_asset(
            asset=record,
            member_role=context.get("member_role") or "viewer",
            relationship_scope=context.get("relationship_scope") or "household_member",
            link_status=context.get("link_status") or "active",
            is_owner=user_id == _normalize_value(record.get("uploaded_by_user_id")),
        )
    ]
    return {"family_id": family_id, "count": len(visible), "items": _serialize_uploads(visible)}


@router.get("/{upload_id}/download")
def download_upload(
    upload_id: str,
    admin_override: bool = Query(default=False),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    upload_record, _context = _require_upload_access(
        upload_id,
        db,
        current_user,
        detail="Your active package does not include upload access.",
    )
    if bool(upload_record.get("quarantined")):
        is_admin = _is_admin(current_user)
        if not (
            is_admin
            and admin_override
            and bool(settings.upload_allow_admin_quarantine_override)
        ):
            try:
                create_audit_log(
                    "private_file_access_denied",
                    _current_user_id(current_user),
                    "upload",
                    upload_id,
                    {"reason": "quarantined"},
                )
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This file is quarantined and cannot be downloaded.",
            )

    if _normalize_value(upload_record.get("storage_provider")).lower() == "r2":
        storage_key = _normalize_value(upload_record.get("storage_key") or upload_record.get("relative_path"))
        signed_url = generate_private_download_url(key=storage_key, expires_seconds=120)
        if not signed_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Private object storage is unavailable for this upload.",
            )
        response = RedirectResponse(url=signed_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

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

    upload_record, _context = _require_upload_management_access(
        upload_id,
        db,
        current_user,
    )

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
