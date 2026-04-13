from __future__ import annotations

import re
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
from fastapi.responses import FileResponse
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
    store_verification_evidence_upload,
)
from app.services.tree_service import list_linked_family_ids
from app.services.workspace_access_service import (
    count_workspace_uploads,
    require_workspace_capability,
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
ALLOWED_VAULT_SCOPE = {"personal", "family_shared"}
ALLOWED_VISIBILITY_SCOPE = {"private", "family_shared", "linked_family_shared", "internal_only"}


class UploadPrivacyUpdatePayload(BaseModel):
    vault_scope: Literal["personal", "family_shared"] | None = None
    visibility_scope: Literal[
        "private",
        "family_shared",
        "linked_family_shared",
        "internal_only",
    ] | None = None
    customer_visible: bool | None = None
    internal_only: bool | None = None
    share_with_linked_families: bool | None = None
    notes: str = Field(default="", max_length=500)


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
        if (
            bool(upload_record.get("internal_only"))
            or (not bool(upload_record.get("customer_visible")) and not owns_record)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This file is not visible to customers.",
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
    project_owner_user_id = _normalize_value((context.get("project") or {}).get("owner_user_id"))
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
    return normalized if normalized in ALLOWED_VISIBILITY_SCOPE else default


def _visibility_flags(scope: str) -> tuple[bool, bool, bool]:
    normalized_scope = _normalize_visibility_scope(scope, default="private")
    if normalized_scope == "internal_only":
        return False, True, False
    if normalized_scope == "private":
        return False, False, False
    if normalized_scope == "linked_family_shared":
        return True, False, True
    return True, False, False


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


def _apply_customer_visibility_filter(query: dict[str, Any], *, is_admin: bool) -> None:
    if is_admin:
        return
    query["internal_only"] = {"$ne": True}
    query["customer_visible"] = True


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
    _apply_customer_visibility_filter(query, is_admin=bool(context.get("is_admin")))
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
    _apply_customer_visibility_filter(query, is_admin=bool(context.get("is_admin")))
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
        capabilities=("can_upload_verification_docs", "can_upload_portraits"),
        detail="Your active package does not include vault access.",
    )

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    base_family_id = _normalize_value((context.get("family") or {}).get("_id"))
    family_ids = [base_family_id]
    if include_linked_families:
        if not bool((context.get("resolved_entitlements") or {}).get("can_link_households")) and not context.get("is_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your active package does not include linked family vault access.",
            )
        family_ids = list_linked_family_ids(base_family_id)

    query: dict[str, Any] = {
        "family_id": {"$in": [family_id for family_id in family_ids if family_id]},
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
            {"customer_visible": True, "internal_only": {"$ne": True}},
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
    customer_visible, internal_only, share_with_linked = _visibility_flags(visibility_scope)

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

    db["uploaded_files"].update_one(
        {"_id": ObjectId(upload_id)},
        {
            "$set": {
                "vault_scope": next_vault_scope,
                "visibility_scope": visibility_scope,
                "customer_visible": customer_visible,
                "internal_only": internal_only,
                "share_with_linked_families": share_with_linked,
                "privacy_notes": _normalize_value(payload.notes),
            }
        },
    )
    updated = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)}) or upload_record
    return {
        "upload": _public_upload_record(updated),
        "workspace_project_id": _normalize_value((context.get("project") or {}).get("_id")) or None,
    }


@router.get("/{upload_id}/download")
def download_upload(
    upload_id: str,
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

    upload_record, _context = _require_upload_access(
        upload_id,
        db,
        current_user,
        detail="Your active package does not include upload access.",
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
