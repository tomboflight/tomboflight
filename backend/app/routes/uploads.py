from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import inspect
import json
import re
import secrets
import shutil
import tempfile
from pathlib import Path
from typing import Any, Literal, Optional
from urllib.parse import quote

from bson import ObjectId
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, Response
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
from app.services.r2_storage_service import (
    delete_private_object,
    download_private_bytes,
    private_storage_is_configured,
    upload_private_file,
)
from app.services.upload_scan_service import scan_uploaded_file
from app.services.audit_log_service import create_audit_log, write_audit_log
from app.services.privacy_access_service import (
    account_access_is_enabled,
    can_access_cinematic_asset,
    can_access_privacy_scope,
    can_manage_privacy_scope,
    normalize_privacy_scope,
)
from app.services.tree_service import list_linked_family_ids
from app.services.linked_network_service import build_linked_network
from app.services.workspace_access_service import (
    family_is_visible_to_user,
    require_workspace_capability,
    require_workspace_maintenance_write_access,
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
VAULT_FILE_ASSET_TYPE_ALIASES = {
    "vault_photo": "vault_photo",
    "photo": "vault_photo",
    "group_photo": "vault_photo",
    "portrait_photo": "vault_photo",
    "vault_document": "vault_document",
    "document": "vault_document",
}
PRIVATE_MEDIA_ALLOWED_ASSET_TYPES.update(VAULT_FILE_ASSET_TYPE_ALIASES)
PRIVATE_MEDIA_ALLOWED_PRIVACY_SCOPES = {
    "private_to_owner",
    "private_to_owner_and_co_owner",
    "household_private",
    "linked_family_shared",
}
HOUSEHOLD_VAULT_CAPABILITY = "can_use_household_vault"
PERSONAL_VAULT_CAPABILITY = "can_use_personal_vault"
ORGANIZATION_VAULT_CAPABILITY = "can_use_organization_records_vault"
LINKED_FAMILY_VAULT_CAPABILITY = "can_use_linked_household_vault"
VAULT_CAPABILITIES = (
    PERSONAL_VAULT_CAPABILITY,
    HOUSEHOLD_VAULT_CAPABILITY,
    LINKED_FAMILY_VAULT_CAPABILITY,
    ORGANIZATION_VAULT_CAPABILITY,
)
UPLOAD_CATEGORY_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "member_photo": ("can_upload_portraits",),
    "verification_evidence": ("can_upload_verification_docs",),
    # Scope-specific filtering narrows this tuple below.  Keeping every Vault
    # capability here supports legacy rows that were incorrectly labelled
    # personal even when created by a household package.
    "private_media": VAULT_CAPABILITIES,
}
VAULT_SCOPE_CAPABILITY = {
    "personal": PERSONAL_VAULT_CAPABILITY,
    "household": HOUSEHOLD_VAULT_CAPABILITY,
    "family_shared": HOUSEHOLD_VAULT_CAPABILITY,
    "linked_family": LINKED_FAMILY_VAULT_CAPABILITY,
    "organization": ORGANIZATION_VAULT_CAPABILITY,
    "organization_records": ORGANIZATION_VAULT_CAPABILITY,
}

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
ALLOWED_VAULT_SCOPE = {
    "personal",
    "household",
    "family_shared",
    "linked_family",
    "organization",
    "organization_records",
}
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
    vault_scope: Literal[
        "personal",
        "household",
        "family_shared",
        "linked_family",
        "organization",
        "organization_records",
    ] | None = None
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
    review_notes: str = Field(default="", max_length=1000)


class UploadVerificationReviewPayload(BaseModel):
    decision: Literal["approved", "rejected", "needs_correction"]
    review_notes: str = Field(default="", max_length=1000)


class UploadPortraitAttestationPayload(BaseModel):
    consent_attested: bool = False
    authority_attested: bool = False


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


def _upload_category_capabilities(upload_record: dict[str, Any]) -> tuple[str, ...]:
    category = _normalize_value(upload_record.get("category")).lower()
    if category != "private_media":
        return UPLOAD_CATEGORY_CAPABILITIES.get(category, ())

    scope = _normalize_value(upload_record.get("vault_scope")).lower()
    capability = VAULT_SCOPE_CAPABILITY.get(scope)
    if capability == PERSONAL_VAULT_CAPABILITY:
        # Older household-vault rows were persisted as personal.  Accepting the
        # household capability here preserves legitimate retrieval while still
        # excluding unrelated portrait/document upload entitlements.
        return (PERSONAL_VAULT_CAPABILITY, HOUSEHOLD_VAULT_CAPABILITY)
    if capability:
        return (capability,)
    return VAULT_CAPABILITIES


def _context_has_any_capability(
    context: dict[str, Any],
    capabilities: tuple[str, ...],
) -> bool:
    if context.get("is_admin"):
        return True
    entitlements = context.get("resolved_entitlements") or {}
    return any(bool(entitlements.get(capability)) for capability in capabilities)


def _is_upload_owner(
    upload_record: dict[str, Any],
    current_user: dict[str, Any],
) -> bool:
    current_user_id = _current_user_id(current_user)
    uploaded_by_user_id = _normalize_value(upload_record.get("uploaded_by_user_id"))
    return bool(
        current_user_id
        and uploaded_by_user_id
        and current_user_id == uploaded_by_user_id
    )


def _is_project_owner(context: dict[str, Any], current_user: dict[str, Any]) -> bool:
    current_user_id = _current_user_id(current_user)
    owner_user_id = _normalize_value((context.get("project") or {}).get("owner_user_id"))
    return bool(current_user_id and owner_user_id and current_user_id == owner_user_id)


def _context_link_status(context: dict[str, Any]) -> str:
    membership = ((context.get("access_snapshot") or {}).get("membership") or {})
    if isinstance(membership, dict) and "link_status" in membership:
        return _normalize_value(membership.get("link_status")).lower()
    relationship_scope = _normalize_value(context.get("relationship_scope")).lower()
    member_role = _normalize_value(context.get("member_role")).lower()
    if (
        relationship_scope in {"linked_relative", "branch_relative"}
        or member_role in {"linked_relative", "branch_relative"}
    ):
        # Workspace context historically synthesized "active" for a missing
        # membership link. Linked access must instead fail closed.
        return ""
    return _normalize_value(context.get("link_status")).lower()


def _has_retained_upload_lifecycle_access(
    *,
    upload_record: dict[str, Any],
    context: dict[str, Any],
    current_user: dict[str, Any],
) -> bool:
    """Allow owners/co-owners to retrieve/delete existing data after downgrade."""

    if context.get("is_admin") or _is_upload_owner(upload_record, current_user):
        return True
    role = _normalize_value(context.get("member_role")).lower()
    return bool(_is_project_owner(context, current_user) or role in {"billing_owner", "co_owner"})


def _upload_classification(upload_record: dict[str, Any]) -> str:
    return _normalize_privacy_classification(
        upload_record.get("privacy_classification"),
        fallback=_classification_from_flags(
            visibility_scope=_normalize_visibility_scope(
                upload_record.get("visibility_scope"),
                "household_private"
                if bool(upload_record.get("customer_visible", True))
                else "private_to_owner",
            ),
            internal_only=bool(upload_record.get("internal_only")),
            customer_visible=bool(upload_record.get("customer_visible", True)),
        ),
    )


def _resolve_private_upload_vault_item_id(
    upload_record: dict[str, Any],
) -> str | None:
    """Resolve/backfill one exact-current Vault link; ``None`` means conflict.

    Missing denormalized links are inferred only from the canonical current
    pointer.  A retained ``asset_versions`` entry may represent superseded
    history and must never be treated as proof that an unlinked upload is
    current.
    """

    if _normalize_value(upload_record.get("category")).lower() != "private_media":
        return ""
    upload_id = _normalize_value(upload_record.get("_id") or upload_record.get("id"))
    explicit_item_id = _normalize_value(upload_record.get("vault_item_id"))
    if not upload_id:
        return None
    try:
        db = get_database()
    except Exception:
        return None if explicit_item_id else ""
    if db is None:
        return None if explicit_item_id else ""
    try:
        matches = list(
            db["vault_items"].find(
                {
                    "$or": [
                        {"current_upload_id": upload_id},
                        {"upload_id": upload_id},
                    ]
                }
            )
        )
    except Exception:
        return None if explicit_item_id else ""
    matches = [
        item
        for item in matches
        if _normalize_value(item.get("current_upload_id") or item.get("upload_id"))
        == upload_id
    ]
    match_ids = {
        _normalize_value(item.get("_id") or item.get("id"))
        for item in matches
        if _normalize_value(item.get("_id") or item.get("id"))
    }
    if explicit_item_id:
        if match_ids and match_ids != {explicit_item_id}:
            return None
        return explicit_item_id
    if not match_ids:
        return ""
    if len(match_ids) != 1:
        try:
            if ObjectId.is_valid(upload_id):
                db["uploaded_files"].update_one(
                    {"_id": ObjectId(upload_id)},
                    {
                        "$set": {
                            "vault_link_status": "conflict",
                            "vault_link_error": "multiple_reverse_links",
                            "updated_at": datetime.now(UTC).isoformat(),
                        }
                    },
                )
        except Exception:
            pass
        return None
    item = matches[0]
    if _normalize_value(item.get("project_id")) != _normalize_value(
        upload_record.get("project_id")
    ):
        return None
    resolved_item_id = next(iter(match_ids))
    upload_record["vault_item_id"] = resolved_item_id
    try:
        if ObjectId.is_valid(upload_id):
            db["uploaded_files"].update_one(
                {"_id": ObjectId(upload_id), "vault_item_id": {"$in": [None, ""]}},
                {
                    "$set": {
                        "vault_item_id": resolved_item_id,
                        "vault_link_status": "linked",
                        "vault_link_reconciled_at": datetime.now(UTC).isoformat(),
                        "updated_at": datetime.now(UTC).isoformat(),
                    }
                },
            )
    except Exception:
        # The in-memory link is sufficient for this request's canonical auth;
        # persistence can be retried by a later read/reconciliation pass.
        pass
    return resolved_item_id


def _can_access_linked_vault_upload(
    *,
    upload_record: dict[str, Any],
    context: dict[str, Any],
    current_user: dict[str, Any],
    require_current: bool,
) -> bool:
    """Apply canonical Vault release/version/grant policy to linked files."""

    if _normalize_value(upload_record.get("category")).lower() != "private_media":
        return True
    upload_id = _normalize_value(upload_record.get("_id") or upload_record.get("id"))
    project_id = _normalize_value(upload_record.get("project_id"))
    user_id = _current_user_id(current_user)
    if not upload_id or not project_id or not user_id:
        return False
    try:
        from app.services.vault_service import authorize_vault_upload_access

        item = authorize_vault_upload_access(
            upload_id,
            user_id,
            authorized_project_id=project_id,
            requesting_workspace_role=_normalize_value(context.get("member_role")).lower(),
            relationship_scope=_normalize_value(context.get("relationship_scope")).lower(),
            link_status=_context_link_status(context),
            require_current=require_current,
            backfill_legacy_linkage=True,
        )
        resolved_item_id = _normalize_value(item.get("_id") or item.get("id"))
        if resolved_item_id:
            upload_record["vault_item_id"] = resolved_item_id
        return True
    except Exception:
        linkage_status = _normalize_value(upload_record.get("vault_link_status")).lower()
        modern_unlinked = bool(
            _normalize_value(upload_record.get("vault_item_id"))
            or linkage_status
            or "release_state" in upload_record
            or "account_access_enabled" in upload_record
            or "version" in upload_record
        )
        if modern_unlinked:
            # A failed/pending modern link is a recovery state, not a sharing
            # grant.  Only the uploader may retain direct lifecycle access.
            return bool(
                not _normalize_value(upload_record.get("vault_item_id"))
                and linkage_status in {"", "pending", "failed"}
                and _is_upload_owner(upload_record, current_user)
            )
        # Truly legacy released rows predate canonical Vault items.  Preserve
        # their uploader/workspace privacy behavior until a migration can link
        # them; draft/scheduled rows always take the fail-closed branch above.
        return True


def _can_change_linked_vault_privacy(
    *,
    upload_record: dict[str, Any],
    context: dict[str, Any],
    current_user: dict[str, Any],
) -> bool:
    if _normalize_value(upload_record.get("category")).lower() != "private_media":
        return True
    if not _is_upload_owner(upload_record, current_user):
        return False
    upload_id = _normalize_value(upload_record.get("_id") or upload_record.get("id"))
    try:
        from app.services.vault_service import authorize_vault_upload_access

        item = authorize_vault_upload_access(
            upload_id,
            _current_user_id(current_user),
            authorized_project_id=_normalize_value(upload_record.get("project_id")),
            requesting_workspace_role=_normalize_value(context.get("member_role")).lower(),
            relationship_scope=_normalize_value(context.get("relationship_scope")).lower(),
            link_status=_context_link_status(context),
            require_current=True,
            backfill_legacy_linkage=True,
        )
        return _normalize_value(item.get("owner_user_id")) == _current_user_id(current_user)
    except Exception:
        return False


def _sync_linked_vault_item_privacy(
    *,
    upload_record: dict[str, Any],
    current_user: dict[str, Any],
    next_vault_scope: str,
    next_privacy_classification: str,
) -> dict[str, str] | None:
    if _normalize_value(upload_record.get("category")).lower() != "private_media":
        return None
    resolved_vault_item_id = _resolve_private_upload_vault_item_id(upload_record)
    if resolved_vault_item_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vault linkage is inconsistent and must be reconciled before changing privacy.",
        )
    vault_item_id = resolved_vault_item_id
    if not vault_item_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vault linkage must be reconciled before changing file privacy or scope.",
        )
    try:
        from app.schemas.vault import VaultItemUpdate
        from app.services.vault_service import (
            _vault_privacy_for_upload,
            _vault_scope_for_upload,
            update_vault_item,
        )

        old_scope = _vault_scope_for_upload(upload_record)
        old_privacy = _vault_privacy_for_upload(upload_record)
        next_projection = {
            **upload_record,
            "vault_scope": next_vault_scope,
            "privacy_classification": next_privacy_classification,
            "privacy_scope": next_privacy_classification,
            "visibility_scope": next_privacy_classification,
        }
        new_scope = _vault_scope_for_upload(next_projection)
        new_privacy = _vault_privacy_for_upload(next_projection)
        update_vault_item(
            vault_item_id,
            VaultItemUpdate(vault_scope=new_scope, privacy=new_privacy),
            _current_user_id(current_user),
            authorized_project_id=_normalize_value(upload_record.get("project_id")),
        )
        return {
            "vault_item_id": vault_item_id,
            "old_scope": old_scope,
            "old_privacy": old_privacy,
        }
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Vault item owner can change linked file privacy or scope.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Linked Vault privacy could not be synchronized; no upload policy was changed.",
        ) from exc


def _rollback_linked_vault_item_privacy(
    *,
    rollback: dict[str, str] | None,
    upload_record: dict[str, Any],
    current_user: dict[str, Any],
) -> None:
    if not rollback:
        return
    from app.schemas.vault import VaultItemUpdate
    from app.services.vault_service import update_vault_item

    update_vault_item(
        rollback["vault_item_id"],
        VaultItemUpdate(
            vault_scope=rollback["old_scope"],
            privacy=rollback["old_privacy"],
        ),
        _current_user_id(current_user),
        authorized_project_id=_normalize_value(upload_record.get("project_id")),
    )


def _can_access_upload_record(
    *,
    upload_record: dict[str, Any],
    context: dict[str, Any],
    current_user: dict[str, Any],
) -> bool:
    if not account_access_is_enabled(upload_record):
        return False
    owns_record = _is_upload_owner(upload_record, current_user)
    if bool(upload_record.get("internal_only")) and not owns_record:
        return False
    if not bool(upload_record.get("customer_visible", True)) and not owns_record:
        return False
    if not _can_access_classification(
        _upload_classification(upload_record),
        context=context,
        upload_record=upload_record,
        current_user=current_user,
    ):
        return False
    return _can_access_linked_vault_upload(
        upload_record=upload_record,
        context=context,
        current_user=current_user,
        require_current=False,
    )


def _can_manage_upload_record(
    *,
    upload_record: dict[str, Any],
    context: dict[str, Any],
    current_user: dict[str, Any],
) -> bool:
    upload_project_id = _normalize_value(upload_record.get("project_id"))
    context_project_id = _normalize_value(
        (context.get("project") or {}).get("_id")
        or (context.get("project") or {}).get("id")
    )
    # A context from a linked viewer workspace grants read-only access to
    # explicitly shared assets.  Its billing/family-manager role must never be
    # projected onto another family's source project.
    if bool(context.get("linked_viewer_read_only")) or (
        upload_project_id
        and context_project_id
        and upload_project_id != context_project_id
    ):
        return False
    if not account_access_is_enabled(upload_record):
        return bool(context.get("is_admin"))
    if context.get("is_admin"):
        return True

    if not _can_access_linked_vault_upload(
        upload_record=upload_record,
        context=context,
        current_user=current_user,
        require_current=False,
    ):
        return False

    return can_manage_privacy_scope(
        privacy_scope=_upload_classification(upload_record),
        member_role=context.get("member_role") or "viewer",
        is_owner=_is_upload_owner(upload_record, current_user),
        is_project_owner=_is_project_owner(context, current_user),
    )


def _can_list_upload_record(
    *,
    upload_record: dict[str, Any],
    context: dict[str, Any],
    current_user: dict[str, Any],
) -> bool:
    capabilities = _upload_category_capabilities(upload_record)
    if not capabilities:
        return False
    has_category_access = _context_has_any_capability(context, capabilities)
    if not has_category_access and not _has_retained_upload_lifecycle_access(
        upload_record=upload_record,
        context=context,
        current_user=current_user,
    ):
        return False
    if not _can_access_upload_record(
        upload_record=upload_record,
        context=context,
        current_user=current_user,
    ):
        return False
    return _can_access_linked_vault_upload(
        upload_record=upload_record,
        context=context,
        current_user=current_user,
        require_current=True,
    )


def _resolve_upload_list_context(
    *,
    current_user: dict[str, Any],
    project_id: str = "",
    family_id: str = "",
    member_id: str = "",
    category: str = "",
    detail: str,
) -> dict[str, Any]:
    pseudo_record = {"category": category} if category else {}
    capabilities = (
        _upload_category_capabilities(pseudo_record)
        if category
        else tuple(
            dict.fromkeys(
                capability
                for values in UPLOAD_CATEGORY_CAPABILITIES.values()
                for capability in values
            )
        )
    )
    if not capabilities:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This upload category is not available to customers.",
        )
    try:
        return require_workspace_capability(
            current_user,
            project_id=project_id,
            family_id=family_id,
            member_id=member_id,
            capabilities=capabilities,
            detail=detail,
        )
    except HTTPException:
        # Resolve membership so existing rows can still be filtered to the
        # uploader/buyer/co-owner after a package downgrade.
        return resolve_workspace_context(
            current_user,
            project_id=project_id,
            family_id=family_id,
            member_id=member_id,
        )


def _audit_upload_access_denial(
    *,
    upload_id: str,
    current_user: dict[str, Any],
    reason: str,
    upload_record: dict[str, Any],
) -> None:
    try:
        create_audit_log(
            "private_file_access_denied",
            _current_user_id(current_user) or None,
            "upload",
            upload_id,
            {
                "reason": reason,
                "privacy_classification": _upload_classification(upload_record),
                "category": _normalize_value(upload_record.get("category")),
            },
        )
    except Exception:
        pass


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

    if not account_access_is_enabled(upload_record):
        _audit_upload_access_denial(
            upload_id=upload_id,
            current_user=current_user,
            reason="account_access_disabled",
            upload_record=upload_record,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This file is unavailable because account access is disabled.",
        )

    family_id = _normalize_value(upload_record.get("family_id"))
    project_id = _normalize_value(upload_record.get("project_id"))
    capabilities = _upload_category_capabilities(upload_record)
    if not capabilities:
        # A small set of legacy rows predates ``category``.  Do not grant a
        # category capability implicitly, but preserve the uploader's direct
        # retrieval/deletion right after resolving the exact workspace.
        try:
            context = require_workspace_capability(
                current_user,
                project_id=project_id,
                family_id=family_id,
                capabilities=tuple(
                    dict.fromkeys(
                        capability
                        for values in UPLOAD_CATEGORY_CAPABILITIES.values()
                        for capability in values
                    )
                ),
                detail=detail,
            )
        except HTTPException:
            context = resolve_workspace_context(
                current_user,
                project_id=project_id,
                family_id=family_id,
            )
        if not _has_retained_upload_lifecycle_access(
            upload_record=upload_record,
            context=context,
            current_user=current_user,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This legacy upload is available only to its owner or workspace buyer/co-owner.",
            )
    else:
        try:
            context = require_workspace_capability(
                current_user,
                project_id=project_id,
                family_id=family_id,
                capabilities=capabilities,
                detail=detail,
            )
        except HTTPException as capability_error:
            # Existing customer data must remain retrievable after a package
            # downgrade by the uploader, buyer, or co-owner. New writes/replacements
            # still require the exact category capability.
            context = resolve_workspace_context(
                current_user,
                project_id=project_id,
                family_id=family_id,
            )
            if not _has_retained_upload_lifecycle_access(
                upload_record=upload_record,
                context=context,
                current_user=current_user,
            ):
                raise capability_error

    if (
        not context.get("is_admin")
        and project_id
        and _normalize_value(context["project"].get("_id")) != project_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Upload does not belong to the current workspace.",
        )

    if not _can_access_upload_record(
        upload_record=upload_record,
        context=context,
        current_user=current_user,
    ):
        _audit_upload_access_denial(
            upload_id=upload_id,
            current_user=current_user,
            reason="privacy_or_visibility_policy",
            upload_record=upload_record,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied for this file privacy classification.",
        )

    return upload_record, context


def _require_upload_management_access(
    upload_id: str,
    db: Any,
    current_user: dict[str, Any],
    *,
    action: str = "manage",
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

    if not _can_manage_upload_record(
        upload_record=upload_record,
        context=context,
        current_user=current_user,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorized to {action} this upload.",
        )

    return upload_record, context


def _require_linked_cinematic_upload_access(
    upload_id: str,
    viewer_project_id: str,
    db: Any,
    current_user: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Authorize one portrait through the requesting user's linked viewer graph."""

    if not ObjectId.is_valid(upload_id):
        raise HTTPException(status_code=400, detail="Invalid upload id.")
    normalized_viewer_project_id = _normalize_value(viewer_project_id)
    if not normalized_viewer_project_id:
        raise HTTPException(status_code=400, detail="Viewer project id is required.")

    context = require_workspace_capability(
        current_user,
        project_id=normalized_viewer_project_id,
        capabilities=("can_use_viewer",),
        detail="Your active package does not include linked family viewer access.",
    )
    network = build_linked_network(
        normalized_viewer_project_id,
        _current_user_id(current_user),
        workspace_context=context,
    )
    matching_node = next(
        (
            node
            for node in network.get("nodes") or []
            if _normalize_value(node.get("approved_photo_upload_id")) == upload_id
        ),
        None,
    )
    if matching_node is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This portrait is not shared with the requested linked family viewer.",
        )

    upload_record = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)})
    if upload_record is None:
        raise HTTPException(status_code=404, detail="Upload not found.")
    if not (
        _normalize_value(upload_record.get("category")) == "member_photo"
        and _normalize_value(upload_record.get("member_id"))
        == _normalize_value(matching_node.get("id"))
        and _normalize_value(upload_record.get("project_id"))
        == _normalize_value(matching_node.get("source_project_id"))
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Linked portrait provenance does not match the approved family graph.",
        )
    return upload_record, context


def _require_linked_vault_upload_access(
    upload_id: str,
    viewer_project_id: str,
    db: Any,
    current_user: dict[str, Any],
    *,
    require_current: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Authorize a read-only linked-family Vault viewer request.

    The viewer proves access to their own project, both linked-Vault
    entitlements, an approved family graph edge, and the source record's
    explicit linked-sharing policy. Canonical Vault authorization remains the
    final release/current-version gate.
    """

    if not ObjectId.is_valid(upload_id):
        raise HTTPException(status_code=400, detail="Invalid upload id.")
    normalized_viewer_project_id = _normalize_value(viewer_project_id)
    if not normalized_viewer_project_id:
        raise HTTPException(status_code=400, detail="Viewer project id is required.")

    context = require_workspace_capability(
        current_user,
        project_id=normalized_viewer_project_id,
        capabilities=(LINKED_FAMILY_VAULT_CAPABILITY,),
        detail="Your active package does not include linked-family Vault access.",
    )
    if context.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer linked-Vault access requires membership in the viewer workspace.",
        )
    if not bool((context.get("resolved_entitlements") or {}).get("can_link_households")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your active package does not include linked-household access.",
        )

    viewer_family_id = _normalize_value((context.get("family") or {}).get("_id"))
    viewer_context_project_id = _normalize_value(
        (context.get("project") or {}).get("_id")
        or (context.get("project") or {}).get("id")
    )
    if not viewer_family_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The viewer workspace is not connected to a household.",
        )
    upload_record = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)})
    if upload_record is None:
        raise HTTPException(status_code=404, detail="Upload not found.")

    source_family_id = _normalize_value(upload_record.get("family_id"))
    source_project_id = _normalize_value(upload_record.get("project_id"))
    if (
        _normalize_value(upload_record.get("category")).lower() != "private_media"
        or _canonical_vault_scope(upload_record.get("vault_scope")) != "linked_family"
        or _upload_classification(upload_record) != "linked_family_shared"
        or not bool(upload_record.get("share_with_linked_families"))
        or upload_record.get("customer_visible") is not True
        or bool(upload_record.get("internal_only"))
        or not source_family_id
        or source_family_id == viewer_family_id
        or not source_project_id
        or source_project_id == viewer_context_project_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This upload is not explicitly shared with a linked-family Vault.",
        )
    try:
        linked_family_ids = {
            _normalize_value(value)
            for value in list_linked_family_ids(viewer_family_id)
            if _normalize_value(value)
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Linked-family status could not be verified.",
        ) from exc
    if source_family_id not in linked_family_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An accepted household link is required to access this Vault upload.",
        )

    access_snapshot = dict(context.get("access_snapshot") or {})
    membership = dict(access_snapshot.get("membership") or {})
    membership.update(
        {
            "member_role": "linked_relative",
            "relationship_scope": "linked_relative",
            "link_status": "approved",
        }
    )
    access_snapshot["membership"] = membership
    linked_context = {
        **context,
        "access_snapshot": access_snapshot,
        "member_role": "linked_relative",
        "relationship_scope": "linked_relative",
        "link_status": "approved",
        "linked_viewer_read_only": True,
    }
    if not _can_access_upload_record(
        upload_record=upload_record,
        context=linked_context,
        current_user=current_user,
    ) or not _can_access_linked_vault_upload(
        upload_record=upload_record,
        context=linked_context,
        current_user=current_user,
        require_current=require_current,
    ):
        _audit_upload_access_denial(
            upload_id=upload_id,
            current_user=current_user,
            reason="linked_vault_policy",
            upload_record=upload_record,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This linked Vault upload is not released to the viewer.",
        )
    return upload_record, linked_context


def _require_viewer_upload_access(
    upload_id: str,
    viewer_project_id: str,
    db: Any,
    current_user: dict[str, Any],
    *,
    require_current: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Dispatch the existing portrait viewer and linked Vault viewer policies."""

    if not ObjectId.is_valid(upload_id):
        raise HTTPException(status_code=400, detail="Invalid upload id.")
    upload_record = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)})
    if upload_record is None:
        raise HTTPException(status_code=404, detail="Upload not found.")
    category = _normalize_value(upload_record.get("category")).lower()
    if category == "private_media":
        return _require_linked_vault_upload_access(
            upload_id,
            viewer_project_id,
            db,
            current_user,
            require_current=require_current,
        )
    if category == "member_photo":
        return _require_linked_cinematic_upload_access(
            upload_id,
            viewer_project_id,
            db,
            current_user,
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="This upload type is not available through a linked viewer.",
    )


def _public_upload_record(
    record: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
    current_user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    serialized = serialize_upload_record(record)
    serialized.pop("relative_path", None)
    serialized.pop("absolute_path", None)
    serialized.pop("storage_path", None)
    serialized.pop("uploaded_by_user_id", None)
    serialized.pop("master_review_notes", None)
    serialized.pop("verification_review_notes", None)
    serialized.pop("verified_by", None)
    serialized.pop("scan_detail", None)
    serialized.pop("quarantine_reason", None)
    can_access = False
    can_manage = False
    can_create_next_version = False
    if context is not None and current_user is not None:
        can_access = _can_access_upload_record(
            upload_record=record,
            context=context,
            current_user=current_user,
        )
        can_manage = _can_manage_upload_record(
            upload_record=record,
            context=context,
            current_user=current_user,
        )
        can_create_next_version = bool(
            _context_has_any_capability(
                context,
                _upload_category_capabilities(record),
            )
            and can_manage
        )
        if (
            _normalize_value(record.get("category")).lower() == "private_media"
            and not bool(
                (context.get("maintenance_access") or {}).get(
                    "write_allowed",
                    True,
                )
            )
        ):
            can_manage = False
            can_create_next_version = False
    download_ready = bool(
        can_access
        and not _upload_scan_blocks_download(record)
        and _upload_has_durable_private_storage(record)
    )
    serialized["permissions"] = {
        "can_preview": download_ready,
        "can_download": download_ready,
        "can_replace": bool(
            can_create_next_version
            and record.get("is_current_version", True)
            and not _normalize_value(record.get("superseded_by_upload_id"))
            and not _normalize_value(record.get("pending_replacement_upload_id"))
        ),
        "can_delete": can_manage,
        "can_change_privacy": bool(
            can_manage
            and context is not None
            and current_user is not None
            and _can_change_linked_vault_privacy(
                upload_record=record,
                context=context,
                current_user=current_user,
            )
        ),
        "can_manage": can_manage,
    }
    return serialized


def _serialize_uploads(
    records: list[dict[str, Any]],
    *,
    context: dict[str, Any] | None = None,
    current_user: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    return [
        _public_upload_record(
            record,
            context=context,
            current_user=current_user,
        )
        for record in records
    ]


def _display_member_name(member: dict[str, Any] | None) -> str | None:
    if not isinstance(member, dict):
        return None

    first_name = _normalize_value(member.get("first_name"))
    last_name = _normalize_value(member.get("last_name"))
    display_name = f"{first_name} {last_name}".strip()
    return display_name or _normalize_value(member.get("display_name")) or None


def _find_reference_record(db: Any, collection_name: str, value: Any) -> dict[str, Any] | None:
    normalized = _normalize_value(value)
    if not normalized:
        return None
    collection = db[collection_name]
    if ObjectId.is_valid(normalized):
        record = collection.find_one({"_id": ObjectId(normalized)})
        if record is not None:
            return record
    return collection.find_one({"id": normalized})


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

    if project_id:
        project = _find_reference_record(db, "projects", project_id)
    if family_id:
        family = _find_reference_record(db, "families", family_id)
    if member_id:
        member = _find_reference_record(db, "family_members", member_id)

    preview_blockers = _admin_preview_blockers(record)
    preview_messages = {
        "security_scan_not_clean": "Run the security scan and obtain a clean verdict before previewing this file.",
        "durable_private_storage_missing": "Private storage migration must complete before preview.",
    }

    return {
        **serialized,
        "project_id": project_id or None,
        "project_name": _normalize_value((project or {}).get("project_name") or (project or {}).get("name")) or None,
        "project_owner_email": _normalize_email((project or {}).get("owner_email")) or None,
        "family_id": family_id or None,
        "family_name": _normalize_value((family or {}).get("family_name")) or None,
        "member_id": member_id or None,
        "member_name": _display_member_name(member),
        "orphaned_project_reference": bool(project_id and project is None),
        "orphaned_family_reference": bool(family_id and family is None),
        "orphaned_member_reference": bool(member_id and member is None),
        "durable_private_storage": _upload_has_durable_private_storage(record),
        "preview_available": not preview_blockers,
        "preview_blockers": preview_blockers,
        "preview_blocker_message": " ".join(
            preview_messages[code]
            for code in preview_blockers
            if code in preview_messages
        ) or None,
        "possible_duplicate": int(record.get("_possible_duplicate_count") or 0) > 1,
        "possible_duplicate_count": int(record.get("_possible_duplicate_count") or 0),
        "master_review_notes": _normalize_value(
            record.get("master_review_notes")
        ),
        "verification_review_notes": _normalize_value(
            record.get("verification_review_notes")
        ),
        "verified_by": _normalize_value(record.get("verified_by")) or None,
    }


def _admin_review_record_identity(record: dict[str, Any]) -> str:
    """Identify one physical review file without hiding distinct uploads.

    Historical migrations can leave multiple Mongo documents pointing at the
    same private object or staging file. Those records should render once, but
    two uploads that merely share a person, filename, or size remain distinct.
    """

    category = _normalize_value(record.get("category")).lower() or "upload"
    for field in ("storage_key", "relative_path", "stored_filename"):
        value = _normalize_value(record.get(field))
        if value:
            return f"{category}:{field}:{value}"
    record_id = _normalize_value(record.get("_id") or record.get("id"))
    return f"{category}:record:{record_id}"


def _admin_review_semantic_identity(record: dict[str, Any]) -> str:
    """Group duplicate-looking records without suppressing distinct uploads."""

    filename = _normalize_value(record.get("original_filename")).lower()
    if not filename:
        return ""
    scope = _normalize_value(
        record.get("member_id")
        or record.get("family_id")
        or record.get("project_id")
        or record.get("uploaded_by_user_id")
        or record.get("uploaded_by")
    ).lower()
    if not scope:
        return ""
    return ":".join(
        [
            _normalize_value(record.get("category")).lower() or "upload",
            scope,
            _normalize_value(
                record.get("verification_type") or record.get("evidence_kind")
            ).lower(),
            filename,
            _normalize_value(
                record.get("file_size") or record.get("size_bytes") or record.get("size")
            ),
        ]
    )


def _deduplicate_admin_review_records(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    deduplicated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        identity = _admin_review_record_identity(record)
        if identity in seen:
            continue
        seen.add(identity)
        deduplicated.append(record)
    semantic_counts: dict[str, int] = {}
    for record in deduplicated:
        semantic_identity = _admin_review_semantic_identity(record)
        if semantic_identity:
            semantic_counts[semantic_identity] = semantic_counts.get(semantic_identity, 0) + 1
    for record in deduplicated:
        semantic_identity = _admin_review_semantic_identity(record)
        record["_possible_duplicate_count"] = semantic_counts.get(semantic_identity, 0)
    return deduplicated, len(records) - len(deduplicated)


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
    quarantine_root = Path(settings.upload_quarantine_root_path).resolve()
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


def _absolute_quarantine_path(quarantine_path: str) -> Path:
    quarantine_root = Path(settings.upload_quarantine_root_path).resolve()
    candidate = Path(quarantine_path).resolve()
    try:
        candidate.relative_to(quarantine_root)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stored quarantine path is invalid.",
        )
    return candidate


def _safe_storage_token(value: Any, *, fallback: str) -> str:
    token = "".join(
        character
        for character in _normalize_value(value)
        if character.isalnum() or character in {"-", "_"}
    ).strip("_-")
    return token or fallback


def _private_storage_key(upload_record: dict[str, Any], upload_id: str) -> str:
    category = _safe_storage_token(upload_record.get("category"), fallback="upload")
    family_id = _safe_storage_token(upload_record.get("family_id"), fallback="family")
    member_id = _safe_storage_token(upload_record.get("member_id"), fallback="member")
    stored_filename = _safe_storage_token(
        upload_record.get("stored_filename"),
        fallback="private-object",
    )
    upload_token = _safe_storage_token(upload_id, fallback=secrets.token_hex(12))
    return (
        f"private-uploads/v1/{category}/{family_id}/{member_id}/"
        f"{upload_token}/{stored_filename}"
    )


def _update_member_photo_scan_status(
    *,
    db: Any,
    upload_record: dict[str, Any],
    upload_id: str,
    photo_submission_status: str,
) -> None:
    if _normalize_value(upload_record.get("category")) != "member_photo":
        return
    member_id = _normalize_value(upload_record.get("member_id"))
    if not ObjectId.is_valid(member_id):
        return
    try:
        db["family_members"].update_one(
            {
                "_id": ObjectId(member_id),
                "pending_photo_upload_id": upload_id,
            },
            {
                "$set": {
                    "photo_submission_status": photo_submission_status,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            },
        )
    except Exception:
        # The upload record remains authoritative if auxiliary member-state
        # bookkeeping needs reconciliation.
        pass


def _quarantine_upload(
    *,
    db: Any,
    upload_record: dict[str, Any],
    upload_id: str,
    absolute_path: Path,
    status_value: str,
    detail: str,
) -> None:
    relative_path = _normalize_value(upload_record.get("relative_path"))
    quarantine_path = _quarantine_path_for_upload(relative_path)
    quarantined = False
    quarantine_detail = detail[:500] or status_value
    if absolute_path.exists():
        try:
            quarantine_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(absolute_path), str(quarantine_path))
            quarantined = True
        except OSError:
            quarantine_detail = f"{quarantine_detail}; move_failed"
    now = datetime.now(UTC).isoformat()
    db["uploaded_files"].update_one(
        {"_id": ObjectId(upload_id)},
        {
            "$set": {
                "scan_status": status_value,
                "scan_detail": quarantine_detail,
                "quarantined": quarantined,
                "quarantine_reason": quarantine_detail,
                "quarantine_path": str(quarantine_path) if quarantined else "",
                "storage_promotion_status": "blocked",
                "updated_at": now,
            }
        },
    )
    _update_member_photo_scan_status(
        db=db,
        upload_record=upload_record,
        upload_id=upload_id,
        photo_submission_status="quarantined",
    )


def _promote_clean_upload_to_private_storage(
    *,
    db: Any,
    upload_record: dict[str, Any],
    upload_id: str,
    absolute_path: Path,
    scan_detail: str,
) -> None:
    storage_key = _private_storage_key(upload_record, upload_id)
    started_at = datetime.now(UTC).isoformat()
    start_result = db["uploaded_files"].update_one(
        {"_id": ObjectId(upload_id)},
        {
            "$set": {
                "storage_promotion_status": "in_progress",
                "storage_key_candidate": storage_key,
                "storage_promotion_started_at": started_at,
                "updated_at": started_at,
            }
        },
    )
    if getattr(start_result, "matched_count", 1) != 1:
        raise RuntimeError("Upload record disappeared before storage promotion.")
    try:
        storage_result = upload_private_file(
            key=storage_key,
            path=absolute_path,
            content_type=_normalize_value(upload_record.get("content_type"))
            or "application/octet-stream",
            metadata={
                "upload-id": upload_id,
                "category": _safe_storage_token(
                    upload_record.get("category"),
                    fallback="upload",
                ),
            },
        )
    except Exception:
        # The provider may have accepted the object before a connection error.
        # A deterministic key makes this cleanup safe and idempotent.
        try:
            delete_private_object(key=storage_key)
        except Exception:
            pass
        raise
    now = datetime.now(UTC).isoformat()
    try:
        update_result = db["uploaded_files"].update_one(
            {"_id": ObjectId(upload_id)},
            {
                "$set": {
                    "scan_status": "clean",
                    "scan_detail": scan_detail[:500],
                    "quarantined": False,
                    "quarantine_reason": "",
                    "quarantine_path": "",
                    "storage_provider": "r2",
                    "storage_bucket": storage_result.get("bucket"),
                    "storage_key": storage_key,
                    "storage_key_candidate": "",
                    "storage_promotion_status": "complete",
                    "storage_promoted_at": now,
                    "local_staging_deleted": False,
                    "updated_at": now,
                }
            },
        )
        if getattr(update_result, "matched_count", 1) != 1:
            raise RuntimeError("Upload record disappeared during storage promotion.")
    except Exception:
        try:
            delete_private_object(key=storage_key)
        except Exception:
            pass
        raise

    local_staging_deleted = False
    try:
        absolute_path.unlink(missing_ok=True)
        local_staging_deleted = True
    except OSError:
        local_staging_deleted = False
    try:
        db["uploaded_files"].update_one(
            {"_id": ObjectId(upload_id)},
            {
                "$set": {
                    "local_staging_deleted": local_staging_deleted,
                    "local_staging_cleanup_pending": not local_staging_deleted,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            },
        )
    except Exception:
        # R2 and the first database update are already authoritative. A later
        # maintenance pass can reconcile any leftover staging file.
        pass
    _update_member_photo_scan_status(
        db=db,
        upload_record=upload_record,
        upload_id=upload_id,
        photo_submission_status="pending_master_review",
    )


def _scan_and_quarantine_upload(*, db: Any, upload_record: dict[str, Any]) -> dict[str, Any]:
    upload_id = str(upload_record.get("id") or upload_record.get("_id") or "")
    relative_path = _normalize_value(upload_record.get("relative_path"))
    if not upload_id or not relative_path:
        return upload_record
    stored_record = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)})
    if stored_record:
        upload_record = stored_record
        relative_path = _normalize_value(upload_record.get("relative_path"))
    absolute_path = _absolute_upload_path(relative_path)
    result = scan_uploaded_file(str(absolute_path))
    if result.status in {"infected", "error", "skipped"}:
        _quarantine_upload(
            db=db,
            upload_record=upload_record,
            upload_id=upload_id,
            absolute_path=absolute_path,
            status_value=result.status,
            detail=result.detail,
        )
    elif result.status == "clean" and private_storage_is_configured():
        try:
            _promote_clean_upload_to_private_storage(
                db=db,
                upload_record=upload_record,
                upload_id=upload_id,
                absolute_path=absolute_path,
                scan_detail=result.detail,
            )
        except Exception as exc:
            _quarantine_upload(
                db=db,
                upload_record=upload_record,
                upload_id=upload_id,
                absolute_path=absolute_path,
                status_value="error",
                detail=f"private_storage_promotion_failed:{type(exc).__name__}",
            )
    elif result.status == "clean" and settings.is_production_environment:
        _quarantine_upload(
            db=db,
            upload_record=upload_record,
            upload_id=upload_id,
            absolute_path=absolute_path,
            status_value="error",
            detail="private_storage_not_configured",
        )
    elif result.status == "clean":
        db["uploaded_files"].update_one(
            {"_id": ObjectId(upload_id)},
            {
                "$set": {
                    "scan_status": result.status,
                    "scan_detail": result.detail[:500],
                    "quarantined": False,
                    "storage_promotion_status": "local_development_only",
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            },
        )
        _update_member_photo_scan_status(
            db=db,
            upload_record=upload_record,
            upload_id=upload_id,
            photo_submission_status="pending_master_review",
        )
    else:
        _quarantine_upload(
            db=db,
            upload_record=upload_record,
            upload_id=upload_id,
            absolute_path=absolute_path,
            status_value="error",
            detail="scanner_returned_non_clean_verdict",
        )
    refreshed = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)})
    return refreshed or upload_record


def _upload_scan_blocks_download(upload_record: dict[str, Any]) -> bool:
    scan_status = _normalize_value(upload_record.get("scan_status")).lower()
    deletion_status = _normalize_value(upload_record.get("deletion_status")).lower()
    return (
        deletion_status in {"pending", "failed"}
        or bool(upload_record.get("quarantined"))
        or scan_status != "clean"
    )


def _upload_has_durable_private_storage(upload_record: dict[str, Any]) -> bool:
    if not settings.is_production_environment:
        return True
    return bool(
        _normalize_value(upload_record.get("storage_provider")).lower() == "r2"
        and _normalize_value(upload_record.get("storage_key"))
    )


def _admin_preview_blockers(upload_record: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if _upload_scan_blocks_download(upload_record):
        blockers.append("security_scan_not_clean")
    if not _upload_has_durable_private_storage(upload_record):
        blockers.append("durable_private_storage_missing")
    return blockers


def _upload_read_limit(upload_record: dict[str, Any]) -> int:
    category = _normalize_value(upload_record.get("category")).lower()
    if category == "member_photo":
        return int(PHOTO_MAX_BYTES)
    return int(EVIDENCE_MAX_BYTES)


def _private_content_disposition(filename: Any, *, disposition: str) -> str:
    safe_name = Path(_normalize_value(filename) or "vault-file").name
    safe_name = "".join(
        character
        for character in safe_name
        if character.isprintable() and character not in {"/", "\\", '"'}
    ).strip() or "vault-file"
    ascii_fallback = safe_name.encode("ascii", "ignore").decode("ascii").strip()
    ascii_fallback = re.sub(r"[^A-Za-z0-9._ -]", "_", ascii_fallback) or "vault-file"
    encoded_name = quote(safe_name, safe="")
    return (
        f'{disposition}; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{encoded_name}"
    )


def _actor_audit_identity(current_user: dict[str, Any]) -> dict[str, str | None]:
    return {
        "user_id": _normalize_value(
            current_user.get("_id")
            or current_user.get("id")
            or current_user.get("user_id")
        )
        or None,
        "email": _normalize_email(current_user.get("email")) or None,
        "name": _normalize_value(
            current_user.get("full_name") or current_user.get("name")
        )
        or None,
    }


def preview_admin_upload_action(
    *,
    upload_id: str,
    action: str,
    decision: str = "",
) -> dict[str, Any]:
    if not ObjectId.is_valid(upload_id):
        raise ValueError("Invalid upload id.")
    db = get_database()
    upload_record = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)})
    if upload_record is None:
        raise ValueError("Upload not found.")

    normalized_action = _normalize_value(action).lower()
    normalized_decision = _normalize_value(decision).lower()
    category = _normalize_value(upload_record.get("category")).lower()
    scan_status = _normalize_value(upload_record.get("scan_status")).lower() or "pending"
    blockers: list[str] = []
    if normalized_action == "portrait_review":
        if category != "member_photo":
            blockers.append("not_a_member_portrait")
        if _normalize_value(upload_record.get("project_id")) and not _find_reference_record(
            db, "projects", upload_record.get("project_id")
        ):
            blockers.append("orphaned_project_reference")
        if _normalize_value(upload_record.get("member_id")) and not _find_reference_record(
            db, "family_members", upload_record.get("member_id")
        ):
            blockers.append("orphaned_member_reference")
        if _normalize_value(upload_record.get("family_id")) and not _find_reference_record(
            db, "families", upload_record.get("family_id")
        ):
            blockers.append("orphaned_family_reference")
        if normalized_decision == "approved":
            if scan_status != "clean" or bool(upload_record.get("quarantined")):
                blockers.append("security_scan_not_clean")
            if not bool(upload_record.get("consent_attested")):
                blockers.append("customer_consent_attestation_missing")
            if not bool(upload_record.get("authority_attested")):
                blockers.append("upload_authority_attestation_missing")
            if not _upload_has_durable_private_storage(upload_record):
                blockers.append("durable_private_storage_missing")
    elif normalized_action == "evidence_review":
        if category != "verification_evidence":
            blockers.append("not_verification_evidence")
        if _normalize_value(upload_record.get("project_id")) and not _find_reference_record(
            db, "projects", upload_record.get("project_id")
        ):
            blockers.append("orphaned_project_reference")
        if _normalize_value(upload_record.get("family_id")) and not _find_reference_record(
            db, "families", upload_record.get("family_id")
        ):
            blockers.append("orphaned_family_reference")
        if normalized_decision == "approved":
            if scan_status != "clean" or bool(upload_record.get("quarantined")):
                blockers.append("security_scan_not_clean")
            if not _upload_has_durable_private_storage(upload_record):
                blockers.append("durable_private_storage_missing")
    elif normalized_action == "upload_rescan":
        if category not in ALLOWED_QUERY_CATEGORIES:
            blockers.append("unsupported_upload_category")
        if _normalize_value(upload_record.get("deletion_status")).lower() in {
            "pending",
            "failed",
        }:
            blockers.append("deletion_reconciliation_pending")
        storage_provider = _normalize_value(upload_record.get("storage_provider")).lower()
        if storage_provider == "r2" and not _normalize_value(upload_record.get("storage_key")):
            blockers.append("private_storage_key_missing")
        if storage_provider != "r2":
            relative_path = _normalize_value(upload_record.get("relative_path"))
            if not relative_path or not _absolute_upload_path(relative_path).exists():
                blockers.append("staged_upload_file_missing")
    else:
        raise ValueError("Unsupported upload review action.")

    return {
        "upload_id": upload_id,
        "action": normalized_action,
        "decision": normalized_decision or None,
        "category": category,
        "scan_status": scan_status,
        "quarantined": bool(upload_record.get("quarantined")),
        "consent_attested": bool(upload_record.get("consent_attested")),
        "authority_attested": bool(upload_record.get("authority_attested")),
        "durable_private_storage": _upload_has_durable_private_storage(upload_record),
        "blocked": bool(blockers),
        "blocked_reasons": blockers,
        "records_to_write": ["uploaded_files", "family_members", "audit_logs"],
    }


def admin_rescan_upload(
    *,
    upload_id: str,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    preview = preview_admin_upload_action(
        upload_id=upload_id,
        action="upload_rescan",
    )
    if preview.get("blocked"):
        raise ValueError(
            "Upload cannot be rescanned: "
            + ", ".join(preview.get("blocked_reasons") or [])
        )

    db = get_database()
    upload_record = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)})
    if upload_record is None:
        raise ValueError("Upload not found.")

    storage_provider = _normalize_value(upload_record.get("storage_provider")).lower()
    if storage_provider == "r2":
        storage_key = _normalize_value(upload_record.get("storage_key"))
        payload = download_private_bytes(
            key=storage_key,
            max_bytes=_upload_read_limit(upload_record),
        )
        staging_root = Path(settings.upload_root_path).resolve() / "admin_rescan"
        staging_root.mkdir(parents=True, exist_ok=True)
        suffix = Path(_normalize_value(upload_record.get("original_filename"))).suffix[:10]
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=staging_root,
                prefix=f"{upload_id}-",
                suffix=suffix or ".bin",
                delete=False,
            ) as handle:
                handle.write(payload)
                temporary_path = Path(handle.name)
            result = scan_uploaded_file(str(temporary_path))
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        normalized_scan_status = _normalize_value(result.status).lower()
        is_clean = normalized_scan_status == "clean"
        now = datetime.now(UTC).isoformat()
        actor = _actor_audit_identity(current_user)
        db["uploaded_files"].update_one(
            {"_id": ObjectId(upload_id)},
            {
                "$set": {
                    "scan_status": normalized_scan_status or "error",
                    "scan_detail": _normalize_value(result.detail)[:500],
                    "quarantined": not is_clean,
                    "quarantine_reason": ""
                    if is_clean
                    else _normalize_value(result.detail)[:500],
                    "storage_promotion_status": "complete"
                    if is_clean
                    else "blocked",
                    "last_admin_rescan_at": now,
                    "last_admin_rescan_by_user_id": actor["user_id"],
                    "updated_at": now,
                }
            },
        )
        _update_member_photo_scan_status(
            db=db,
            upload_record=upload_record,
            upload_id=upload_id,
            photo_submission_status=(
                "pending_master_review" if is_clean else "quarantined"
            ),
        )
    else:
        refreshed = _scan_and_quarantine_upload(
            db=db,
            upload_record=upload_record,
        )
        normalized_scan_status = _normalize_value(
            refreshed.get("scan_status")
        ).lower()

    actor = _actor_audit_identity(current_user)
    write_audit_log(
        actor_user_id=actor["user_id"],
        actor_email=actor["email"],
        actor_name=actor["name"],
        action="uploads.admin.security_rescan",
        target_type="upload",
        target_id=upload_id,
        before={
            "scan_status": preview.get("scan_status"),
            "quarantined": preview.get("quarantined"),
        },
        after={"scan_status": normalized_scan_status},
        context={"surface": "admin_upload_review"},
    )
    updated = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)}) or upload_record
    return {"upload": _public_upload_record(updated)}


def _clear_deleted_member_photo_references(
    *,
    db: Any,
    upload_record: dict[str, Any],
    upload_id: str,
    current_user: dict[str, Any],
) -> None:
    if _normalize_value(upload_record.get("category")) != "member_photo":
        return
    member_id = _normalize_value(upload_record.get("member_id"))
    if not ObjectId.is_valid(member_id):
        return

    member = db["family_members"].find_one({"_id": ObjectId(member_id)})
    if not member:
        return

    pending_matches = (
        _normalize_value(member.get("pending_photo_upload_id")) == upload_id
    )
    approved_matches = (
        _normalize_value(member.get("approved_photo_upload_id")) == upload_id
    )
    active_matches = _normalize_value(member.get("photo_upload_id")) == upload_id
    if not (pending_matches or approved_matches or active_matches):
        return

    member_update: dict[str, Any] = {
        "updated_at": datetime.now(UTC).isoformat(),
        "updated_by": _actor_label(current_user),
        "updated_by_user_id": _current_user_id(current_user),
    }
    if pending_matches:
        member_update["pending_photo_upload_id"] = None
    if approved_matches:
        member_update["approved_photo_upload_id"] = None
        member_update["portrait_approved_at"] = None
    if active_matches:
        member_update.update(
            {
                "photo_upload_id": None,
                "photo_path": None,
                "photo_original_filename": None,
                "photo_content_type": None,
                "photo_size_bytes": 0,
            }
        )

    other_active = bool(
        (
            _normalize_value(member.get("approved_photo_upload_id"))
            and not approved_matches
        )
        or (
            _normalize_value(member.get("photo_upload_id"))
            and not active_matches
        )
    )
    other_pending = bool(
        _normalize_value(member.get("pending_photo_upload_id"))
        and not pending_matches
    )
    if other_active:
        member_update["photo_submission_status"] = "approved"
    elif not other_pending:
        member_update["photo_submission_status"] = "not_submitted"

    result = db["family_members"].update_one(
        {"_id": ObjectId(member_id)},
        {"$set": member_update},
    )
    if getattr(result, "matched_count", 1) != 1:
        raise RuntimeError("Family member disappeared during upload deletion.")


def _deletion_tombstone_id(upload_id: str) -> str:
    return f"upload_delete_{upload_id}"


def _create_upload_deletion_tombstone(
    *,
    db: Any,
    upload_record: dict[str, Any],
    upload_id: str,
    current_user: dict[str, Any],
) -> str:
    tombstone_id = _deletion_tombstone_id(upload_id)
    now = datetime.now(UTC).isoformat()
    tombstone = {
        "_id": tombstone_id,
        "upload_id": upload_id,
        "project_id": _normalize_value(upload_record.get("project_id")) or None,
        "family_id": _normalize_value(upload_record.get("family_id")) or None,
        "member_id": _normalize_value(upload_record.get("member_id")) or None,
        "category": _normalize_value(upload_record.get("category")) or None,
        "asset_type": _normalize_value(upload_record.get("asset_type")) or None,
        "vault_item_id": _normalize_value(upload_record.get("vault_item_id")) or None,
        "version_group_id": _normalize_value(
            upload_record.get("version_group_id") or upload_record.get("_id")
        )
        or None,
        "version": max(_as_int(upload_record.get("version"), 1), 1),
        "replaces_upload_id": _normalize_value(upload_record.get("replaces_upload_id")) or None,
        "superseded_by_upload_id": _normalize_value(
            upload_record.get("superseded_by_upload_id")
        )
        or None,
        "original_filename_sha256": hashlib.sha256(
            _normalize_value(upload_record.get("original_filename")).encode("utf-8")
        ).hexdigest(),
        "storage_reference_sha256": hashlib.sha256(
            _normalize_value(
                upload_record.get("storage_key")
                or upload_record.get("relative_path")
                or upload_record.get("quarantine_path")
            ).encode("utf-8")
        ).hexdigest(),
        "size_bytes": max(_as_int(upload_record.get("size_bytes"), 0), 0),
        "content_type": _normalize_value(upload_record.get("content_type")) or None,
        "requested_by_user_id": _current_user_id(current_user) or None,
        "status": "pending",
        "detail": "",
        "requested_at": now,
        "updated_at": now,
    }
    collection = db["upload_deletion_tombstones"]
    try:
        collection.insert_one(tombstone)
    except Exception as exc:
        existing = collection.find_one({"_id": tombstone_id})
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Deletion audit storage is unavailable; no file was removed.",
            ) from exc
        collection.update_one(
            {"_id": tombstone_id},
            {
                "$set": {
                    "status": "pending",
                    "detail": "retry",
                    "requested_by_user_id": _current_user_id(current_user) or None,
                    "updated_at": now,
                }
            },
        )
    return tombstone_id


def _update_upload_deletion_tombstone(
    *,
    db: Any,
    tombstone_id: str,
    tombstone_status: str,
    detail: str = "",
) -> None:
    result = db["upload_deletion_tombstones"].update_one(
        {"_id": tombstone_id},
        {
            "$set": {
                "status": tombstone_status,
                "detail": _normalize_value(detail)[:200],
                "completed_at": (
                    datetime.now(UTC).isoformat()
                    if tombstone_status == "complete"
                    else None
                ),
                "updated_at": datetime.now(UTC).isoformat(),
            }
        },
    )
    if getattr(result, "matched_count", 0) != 1:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Deletion audit could not be checkpointed; the upload record was retained.",
        )


def _tombstone_linked_vault_upload_version(
    *,
    db: Any,
    upload_record: dict[str, Any],
    upload_id: str,
    current_user: dict[str, Any],
    context: dict[str, Any],
    tombstone_id: str,
) -> dict[str, Any] | None:
    if _normalize_value(upload_record.get("category")).lower() != "private_media":
        return None
    resolved_vault_item_id = _resolve_private_upload_vault_item_id(upload_record)
    if resolved_vault_item_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vault linkage is inconsistent; deletion was stopped for reconciliation.",
        )
    if not resolved_vault_item_id:
        return None
    try:
        from app.services.vault_service import (
            preview_vault_upload_version_deletion,
            tombstone_vault_upload_version,
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vault version deletion is temporarily unavailable; no file was removed.",
        ) from exc

    kwargs = {
        "authorized_project_id": _normalize_value(upload_record.get("project_id")),
        "workspace_member_role": _normalize_value(context.get("member_role")).lower(),
    }
    try:
        preview = preview_vault_upload_version_deletion(
            resolved_vault_item_id,
            upload_id,
            _current_user_id(current_user),
            **kwargs,
        )
        if not bool(preview.get("allowed")):
            raise PermissionError("vault_delete_not_allowed")
        result = tombstone_vault_upload_version(
            resolved_vault_item_id,
            upload_id,
            _current_user_id(current_user),
            reason="customer_delete",
            **kwargs,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this linked Vault file version.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vault version state could not be updated; no physical file was removed.",
        ) from exc
    if not bool(result.get("safe_to_delete_upload")):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vault did not confirm that this file version is safe to delete.",
        )

    promoted_upload_id = _normalize_value(result.get("promoted_upload_id"))
    if promoted_upload_id and ObjectId.is_valid(promoted_upload_id):
        db["uploaded_files"].update_one(
            {"_id": ObjectId(promoted_upload_id)},
            {
                "$set": {
                    "is_current_version": True,
                    "replacement_status": "current",
                    "superseded_by_upload_id": None,
                    "version": max(_as_int(result.get("promoted_version"), 1), 1),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            },
        )
    db["upload_deletion_tombstones"].update_one(
        {"_id": tombstone_id},
        {
            "$set": {
                "vault_version_tombstoned": True,
                "vault_was_current": bool(result.get("was_current")),
                "vault_promoted_upload_id": promoted_upload_id or None,
                "vault_item_closed": bool(result.get("item_closed")),
                "updated_at": datetime.now(UTC).isoformat(),
            }
        },
    )
    return result


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
    if not normalized and not _normalize_value(default):
        return ""
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
    raw_value = _normalize_value(value)
    normalized = normalize_privacy_scope(raw_value or fallback)
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
    normalized = _normalize_privacy_classification(classification, fallback="private_to_owner")
    user_id = _current_user_id(current_user)
    uploaded_by_user_id = _normalize_value(upload_record.get("uploaded_by_user_id"))
    return can_access_privacy_scope(
        privacy_scope=normalized,
        member_role=context.get("member_role") or "viewer",
        relationship_scope=context.get("relationship_scope") or "household_member",
        link_status=_context_link_status(context),
        is_owner=bool(user_id and uploaded_by_user_id and user_id == uploaded_by_user_id),
        is_project_owner=_is_project_owner(context, current_user),
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

    compatible_extensions = {
        "image/jpeg": {".jpg", ".jpeg"},
        "image/png": {".png"},
        "image/webp": {".webp"},
        "application/pdf": {".pdf"},
        "audio/mpeg": {".mp3"},
        "audio/mp4": {".m4a", ".mp4"},
        "audio/wav": {".wav"},
        "audio/x-wav": {".wav"},
        "audio/webm": {".webm"},
        "audio/ogg": {".ogg"},
        "video/mp4": {".mp4"},
        "video/webm": {".webm"},
        "video/quicktime": {".mov"},
        "video/ogg": {".ogv", ".ogg"},
    }
    if extension not in compatible_extensions.get(content_type, {extension}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} filename extension does not match its content type.",
        )

    file_handle = upload.file
    original_position = file_handle.tell()
    try:
        file_handle.seek(0)
        header = file_handle.read(32)
    finally:
        file_handle.seek(original_position)

    signature_matches = {
        "image/jpeg": lambda value: len(value) >= 3 and value[:3] == b"\xff\xd8\xff",
        "image/png": lambda value: value.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": lambda value: len(value) >= 12
        and value[:4] == b"RIFF"
        and value[8:12] == b"WEBP",
        "application/pdf": lambda value: value.startswith(b"%PDF-"),
        "audio/mpeg": lambda value: value.startswith(b"ID3")
        or (len(value) >= 2 and value[0] == 0xFF and (value[1] & 0xE0) == 0xE0),
        "audio/mp4": lambda value: len(value) >= 12 and value[4:8] == b"ftyp",
        "audio/wav": lambda value: len(value) >= 12
        and value[:4] == b"RIFF"
        and value[8:12] == b"WAVE",
        "audio/x-wav": lambda value: len(value) >= 12
        and value[:4] == b"RIFF"
        and value[8:12] == b"WAVE",
        "audio/webm": lambda value: value.startswith(b"\x1aE\xdf\xa3"),
        "audio/ogg": lambda value: value.startswith(b"OggS"),
        "video/mp4": lambda value: len(value) >= 12 and value[4:8] == b"ftyp",
        "video/webm": lambda value: value.startswith(b"\x1aE\xdf\xa3"),
        "video/quicktime": lambda value: len(value) >= 12 and value[4:8] == b"ftyp",
        "video/ogg": lambda value: value.startswith(b"OggS"),
    }
    matcher = signature_matches.get(content_type)
    if matcher is None or not matcher(header):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} file signature does not match its declared content type.",
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
    normalized_asset_type = _normalize_value(asset_type).lower()
    entitlement_asset_types = {normalized_asset_type}
    if normalized_asset_type == "vault_photo":
        entitlement_asset_types.update({"group_photo", "portrait_photo"})
    elif normalized_asset_type == "vault_document":
        entitlement_asset_types.add("document")
    if not allowed or not allowed.intersection(entitlement_asset_types):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your active package does not permit this private Vault file type.",
        )


def _canonical_vault_asset_type(value: Any) -> str:
    normalized = _normalize_value(value).lower()
    return VAULT_FILE_ASSET_TYPE_ALIASES.get(normalized, normalized)


def _canonical_vault_scope(value: Any) -> str:
    normalized = _normalize_value(value).lower()
    if normalized in {"family_shared", "household"}:
        return "household"
    if normalized in {"organization", "organization_records"}:
        return "organization"
    if normalized == "linked_family":
        return "linked_family"
    if normalized == "personal":
        return "personal"
    return ""


def _resolve_vault_scope_for_create(
    *,
    context: dict[str, Any],
    requested_scope: Any,
) -> tuple[str, str]:
    entitlements = context.get("resolved_entitlements") or {}
    normalized_scope = _canonical_vault_scope(requested_scope)
    if not normalized_scope:
        for candidate in ("personal", "household", "linked_family", "organization"):
            capability = VAULT_SCOPE_CAPABILITY[candidate]
            if bool(context.get("is_admin")) or bool(entitlements.get(capability)):
                normalized_scope = candidate
                break
    if not normalized_scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your active package does not include a private Vault scope.",
        )
    capability = VAULT_SCOPE_CAPABILITY[normalized_scope]
    if not context.get("is_admin") and not bool(entitlements.get(capability)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your active package does not include the {normalized_scope} Vault.",
        )
    return normalized_scope, capability


def _resolve_upload_release_fields(
    *,
    context: dict[str, Any],
    release_state: Any,
    reveal_at: Any,
) -> tuple[str, str | None]:
    normalized_state = _normalize_value(release_state).lower() or "released"
    if normalized_state not in {"released", "draft", "scheduled"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="release_state must be released, draft, or scheduled.",
        )
    normalized_reveal_at = _normalize_value(reveal_at)
    parsed_reveal_at: datetime | None = None
    if normalized_reveal_at:
        try:
            parsed_reveal_at = datetime.fromisoformat(
                normalized_reveal_at.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="reveal_at must be a valid ISO-8601 datetime with a timezone.",
            ) from exc
        if parsed_reveal_at.tzinfo is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="reveal_at must include a timezone.",
            )
        parsed_reveal_at = parsed_reveal_at.astimezone(UTC)

    if normalized_state == "scheduled":
        if not context.get("is_admin") and not bool(
            (context.get("resolved_entitlements") or {}).get("can_use_scheduled_reveal")
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your active package does not include scheduled Vault release.",
            )
        if parsed_reveal_at is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Scheduled Vault uploads require reveal_at.",
            )
        if parsed_reveal_at <= datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scheduled Vault reveal_at must be in the future.",
            )
    elif parsed_reveal_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="reveal_at is allowed only when release_state is scheduled.",
        )
    return (
        normalized_state,
        parsed_reveal_at.isoformat() if parsed_reveal_at is not None else None,
    )


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _enforce_workspace_upload_limit(context: dict[str, Any], *, db: Any) -> None:
    entitlements = context.get("resolved_entitlements") or {}
    max_uploads = _as_int(entitlements.get("max_uploads"), 0)
    if max_uploads <= 0:
        return

    family_id = _normalize_value((context.get("family") or {}).get("_id"))
    project_id = _normalize_value((context.get("project") or {}).get("_id"))
    query: dict[str, Any] = {
        "account_access_enabled": {"$ne": False},
        "owner_account_deleted": {"$ne": True},
        "replacement_status": {"$nin": ["blocked", "rejected"]},
    }
    if project_id:
        query["project_id"] = project_id
    elif family_id:
        query["family_id"] = family_id
    else:
        return
    logical_asset_ids: set[str] = set()
    for record in db["uploaded_files"].find(query):
        record_id = _normalize_value(record.get("_id") or record.get("id"))
        group_id = _normalize_value(record.get("version_group_id")) or record_id
        if group_id:
            logical_asset_ids.add(group_id)
    current_count = len(logical_asset_ids)
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


def _normalize_idempotency_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = value.strip()
    if not normalized:
        return ""
    if len(normalized) < 8 or len(normalized) > 200 or not normalized.isprintable():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key must contain 8 to 200 printable characters.",
        )
    return normalized


def _idempotency_fingerprint(
    *,
    operation: str,
    current_user: dict[str, Any],
    upload: UploadFile,
    fields: dict[str, Any],
) -> tuple[str, str]:
    file_handle = upload.file
    original_position = file_handle.tell()
    content_digest = hashlib.sha256()
    try:
        file_handle.seek(0)
        while True:
            chunk = file_handle.read(1024 * 1024)
            if not chunk:
                break
            content_digest.update(chunk)
    finally:
        file_handle.seek(original_position)
    normalized_fields = {
        key: _normalize_value(value)
        for key, value in sorted(fields.items())
    }
    payload = {
        "operation": _normalize_value(operation).lower(),
        "user_id": _current_user_id(current_user),
        "filename": _normalize_value(upload.filename),
        "content_type": _normalize_value(upload.content_type).lower(),
        "size_bytes": _upload_size_bytes(upload),
        "content_sha256": content_digest.hexdigest(),
        "fields": normalized_fields,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), json.dumps(payload, sort_keys=True)


def _begin_upload_idempotency(
    *,
    db: Any,
    idempotency_key: Any,
    operation: str,
    current_user: dict[str, Any],
    upload: UploadFile,
    fields: dict[str, Any],
) -> tuple[str, str, dict[str, Any] | None]:
    """Reserve one retry key using Mongo's inherently unique ``_id`` field."""

    normalized_key = _normalize_idempotency_key(idempotency_key)
    if not normalized_key:
        return "", "", None
    user_id = _current_user_id(current_user)
    key_hash = hashlib.sha256(
        f"{user_id}:{_normalize_value(operation).lower()}:{normalized_key}".encode("utf-8")
    ).hexdigest()
    fingerprint_hash, fingerprint_payload = _idempotency_fingerprint(
        operation=operation,
        current_user=current_user,
        upload=upload,
        fields=fields,
    )

    existing_upload = db["uploaded_files"].find_one(
        {"idempotency_key_hash": key_hash}
    )
    if existing_upload is not None:
        if _normalize_value(existing_upload.get("idempotency_fingerprint")) not in {
            "",
            fingerprint_hash,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency-Key was already used for a different upload request.",
            )
        return key_hash, fingerprint_hash, existing_upload

    collection = db["upload_idempotency_keys"]
    reservation = {
        "_id": f"upload_idem_{key_hash}",
        "key_hash": key_hash,
        "fingerprint": fingerprint_hash,
        "fingerprint_payload": fingerprint_payload,
        "operation": _normalize_value(operation).lower(),
        "user_id": user_id,
        "status": "in_progress",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    try:
        collection.insert_one(reservation)
    except Exception:
        existing_upload = db["uploaded_files"].find_one(
            {"idempotency_key_hash": key_hash}
        )
        if existing_upload is not None:
            if _normalize_value(existing_upload.get("idempotency_fingerprint")) not in {
                "",
                fingerprint_hash,
            }:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency-Key was already used for a different upload request.",
                )
            return key_hash, fingerprint_hash, existing_upload
        existing_reservation = collection.find_one({"_id": reservation["_id"]})
        if existing_reservation and _normalize_value(
            existing_reservation.get("fingerprint")
        ) != fingerprint_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency-Key was already used for a different upload request.",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An upload with this Idempotency-Key is already in progress.",
        )
    return key_hash, fingerprint_hash, None


def _finish_upload_idempotency(
    *,
    db: Any,
    key_hash: str,
    upload_record: dict[str, Any],
) -> None:
    if not key_hash:
        return
    upload_id = _normalize_value(upload_record.get("_id") or upload_record.get("id"))
    try:
        db["upload_idempotency_keys"].update_one(
            {"_id": f"upload_idem_{key_hash}"},
            {
                "$set": {
                    "status": "complete",
                    "upload_id": upload_id,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            },
        )
    except Exception:
        # The upload row also contains the deterministic hash and remains the
        # authoritative replay lookup if reservation checkpointing fails.
        pass


def _release_upload_idempotency(*, db: Any, key_hash: str) -> None:
    if not key_hash:
        return
    try:
        existing_upload = db["uploaded_files"].find_one(
            {"idempotency_key_hash": key_hash}
        )
        if existing_upload is None:
            db["upload_idempotency_keys"].delete_one(
                {"_id": f"upload_idem_{key_hash}"}
            )
    except Exception:
        pass


def _upload_status_payload(upload_record: dict[str, Any]) -> dict[str, Any]:
    scan_status = _normalize_value(upload_record.get("scan_status")).lower() or "pending"
    review_status = _normalize_value(upload_record.get("verification_status")).lower() or "pending"
    category = _normalize_value(upload_record.get("category")).lower()
    if not account_access_is_enabled(upload_record):
        state = "blocked"
        message = "Account access is disabled for this file."
    elif bool(upload_record.get("quarantined")) or scan_status in {
        "infected",
        "error",
        "skipped",
    }:
        state = "quarantined"
        message = "The file is quarantined and cannot be opened until security review succeeds."
    elif scan_status != "clean":
        state = "processing"
        message = "The file is awaiting security scanning."
    elif category == "private_media":
        state = "ready"
        message = "The Vault file passed security scanning and is ready."
    elif review_status in {"approved", "rejected", "needs_correction"}:
        state = review_status
        message = f"The upload review status is {review_status.replace('_', ' ')}."
    else:
        state = "pending_review"
        message = "The file passed security scanning and is awaiting review."
    return {
        "state": state,
        "scan_status": scan_status,
        "review_status": review_status,
        "download_ready": bool(
            state in {"ready", "pending_review", "approved"}
            and not _upload_scan_blocks_download(upload_record)
            and _upload_has_durable_private_storage(upload_record)
        ),
        "message": message,
    }


def _resume_replayed_upload(*, db: Any, upload_record: dict[str, Any]) -> dict[str, Any]:
    scan_status = _normalize_value(upload_record.get("scan_status")).lower()
    if (
        scan_status in {"", "pending"}
        and _normalize_value(upload_record.get("relative_path"))
        and not bool(upload_record.get("quarantined"))
    ):
        return _scan_and_quarantine_upload(db=db, upload_record=upload_record)
    return upload_record


def _vault_item_id_from_result(result: Any) -> str:
    if isinstance(result, str):
        return _normalize_value(result)
    if not isinstance(result, dict):
        return ""
    nested = result.get("vault_item")
    if isinstance(nested, dict):
        result = nested
    return _normalize_value(
        result.get("_id")
        or result.get("id")
        or result.get("vault_item_id")
    )


def _ensure_upload_vault_linkage(
    *,
    db: Any,
    upload_record: dict[str, Any],
    current_user: dict[str, Any],
    authorized_project_id: str,
    requested_vault_item_id: str = "",
    workspace_member_role: str = "",
) -> dict[str, Any]:
    """Create/validate the Vault item and link its current file version.

    Authorization is repeated by ``vault_service`` against the supplied
    project/family/member identifiers.  That prevents a client from attaching
    an upload to a Vault item in another workspace merely by guessing its id.
    """

    upload_id = _normalize_value(upload_record.get("_id") or upload_record.get("id"))
    project_id = _normalize_value(authorized_project_id)
    requesting_user_id = _current_user_id(current_user)
    if not upload_id or not ObjectId.is_valid(upload_id):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload persistence did not return a valid file identifier.",
        )
    if not project_id or not requesting_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A verified workspace and customer account are required for Vault linkage.",
        )

    try:
        from app.services.vault_service import (
            ensure_vault_item_for_upload,
            link_vault_upload,
        )

        vault_item_id = _normalize_value(
            requested_vault_item_id or upload_record.get("vault_item_id")
        )
        role_kwargs = (
            {"workspace_member_role": _normalize_value(workspace_member_role).lower()}
            if "workspace_member_role" in inspect.signature(link_vault_upload).parameters
            else {}
        )
        if vault_item_id:
            link_vault_upload(
                vault_item_id,
                upload_id,
                requesting_user_id,
                authorized_project_id=project_id,
                family_id=_normalize_value(upload_record.get("family_id")),
                member_id=_normalize_value(upload_record.get("member_id")),
                version=max(_as_int(upload_record.get("version"), 1), 1),
                replaces_upload_id=_normalize_value(upload_record.get("replaces_upload_id")),
                **role_kwargs,
            )
        else:
            ensure_role_kwargs = (
                {"workspace_member_role": _normalize_value(workspace_member_role).lower()}
                if "workspace_member_role"
                in inspect.signature(ensure_vault_item_for_upload).parameters
                else {}
            )
            ensured = ensure_vault_item_for_upload(
                upload_record,
                requesting_user_id,
                vault_item_id="",
                authorized_project_id=project_id,
                replaces_upload_id=_normalize_value(upload_record.get("replaces_upload_id")),
                **ensure_role_kwargs,
            )
            vault_item_id = _vault_item_id_from_result(ensured)
            if not vault_item_id:
                raise RuntimeError("vault_item_id_missing")
    except HTTPException:
        raise
    except Exception as exc:
        try:
            db["uploaded_files"].update_one(
                {"_id": ObjectId(upload_id)},
                {
                    "$set": {
                        "vault_link_status": "failed",
                        "vault_link_error": type(exc).__name__,
                        "updated_at": datetime.now(UTC).isoformat(),
                    }
                },
            )
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The file was stored safely, but Vault linkage is temporarily unavailable. Retry with the same Idempotency-Key.",
        ) from exc

    now = datetime.now(UTC).isoformat()
    try:
        db["uploaded_files"].update_one(
            {"_id": ObjectId(upload_id)},
            {
                "$set": {
                    "vault_item_id": vault_item_id,
                    "vault_link_status": "linked",
                    "vault_linked_at": now,
                    "vault_link_error": "",
                    "updated_at": now,
                }
            },
        )
        refreshed = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)})
        if refreshed is not None:
            return refreshed
    except Exception:
        # The core link is authoritative.  Preserve the response linkage even
        # if this denormalized cache field needs reconciliation.
        pass
    updated = dict(upload_record)
    updated["vault_item_id"] = vault_item_id
    updated["vault_link_status"] = "linked"
    updated["vault_linked_at"] = now
    return updated


def _validate_replacement_file(
    upload_record: dict[str, Any],
    upload: UploadFile,
) -> None:
    category = _normalize_value(upload_record.get("category")).lower()
    if category == "member_photo":
        _validate_upload_file(
            upload,
            allowed_content_types=PHOTO_ALLOWED_CONTENT_TYPES,
            allowed_extensions=PHOTO_ALLOWED_EXTENSIONS,
            max_bytes=PHOTO_MAX_BYTES,
            label="member photo replacement",
        )
        return
    if category == "verification_evidence":
        _validate_upload_file(
            upload,
            allowed_content_types=EVIDENCE_ALLOWED_CONTENT_TYPES,
            allowed_extensions=EVIDENCE_ALLOWED_EXTENSIONS,
            max_bytes=EVIDENCE_MAX_BYTES,
            label="verification evidence replacement",
        )
        return
    if category != "private_media":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This upload category does not support replacement.",
        )
    asset_type = _canonical_vault_asset_type(upload_record.get("asset_type"))
    if asset_type == "vault_photo":
        _validate_upload_file(
            upload,
            allowed_content_types=PHOTO_ALLOWED_CONTENT_TYPES,
            allowed_extensions=PHOTO_ALLOWED_EXTENSIONS,
            max_bytes=PHOTO_MAX_BYTES,
            label="Vault photo replacement",
        )
    elif asset_type == "vault_document":
        _validate_upload_file(
            upload,
            allowed_content_types=EVIDENCE_ALLOWED_CONTENT_TYPES,
            allowed_extensions=EVIDENCE_ALLOWED_EXTENSIONS,
            max_bytes=EVIDENCE_MAX_BYTES,
            label="Vault document replacement",
        )
    else:
        _validate_upload_file(
            upload,
            allowed_content_types=PRIVATE_MEDIA_ALLOWED_CONTENT_TYPES,
            allowed_extensions=PRIVATE_MEDIA_ALLOWED_EXTENSIONS,
            max_bytes=EVIDENCE_MAX_BYTES,
            label="private media replacement",
        )


def _replacement_is_storage_ready(upload_record: dict[str, Any]) -> bool:
    return bool(
        _normalize_value(upload_record.get("scan_status")).lower() == "clean"
        and not bool(upload_record.get("quarantined"))
        and _upload_has_durable_private_storage(upload_record)
    )


def _claim_upload_replacement(
    *,
    db: Any,
    upload_record: dict[str, Any],
    claim_token: str,
) -> None:
    upload_id = _normalize_value(upload_record.get("_id") or upload_record.get("id"))
    result = db["uploaded_files"].update_one(
        {
            "_id": ObjectId(upload_id),
            "superseded_by_upload_id": {"$in": [None, ""]},
            "replacement_claim_token": {"$in": [None, ""]},
        },
        {
            "$set": {
                "replacement_claim_token": claim_token,
                "replacement_claimed_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
            }
        },
    )
    if getattr(result, "matched_count", 0) != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This upload is already being replaced or has a newer version.",
        )


def _clear_upload_replacement_claim(
    *,
    db: Any,
    upload_id: str,
    claim_token: str,
) -> None:
    if not upload_id or not ObjectId.is_valid(upload_id):
        return
    try:
        db["uploaded_files"].update_one(
            {"_id": ObjectId(upload_id), "replacement_claim_token": claim_token},
            {
                "$set": {
                    "replacement_claim_token": None,
                    "replacement_claimed_at": None,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            },
        )
    except Exception:
        pass


def _apply_replacement_state(
    *,
    db: Any,
    prior_upload: dict[str, Any],
    replacement: dict[str, Any],
    claim_token: str = "",
) -> dict[str, Any]:
    prior_id = _normalize_value(prior_upload.get("_id") or prior_upload.get("id"))
    replacement_id = _normalize_value(replacement.get("_id") or replacement.get("id"))
    if not ObjectId.is_valid(prior_id) or not ObjectId.is_valid(replacement_id):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Replacement persistence returned an invalid identifier.",
        )
    now = datetime.now(UTC).isoformat()
    category = _normalize_value(prior_upload.get("category")).lower()
    if not _replacement_is_storage_ready(replacement):
        db["uploaded_files"].update_one(
            {"_id": ObjectId(replacement_id)},
            {
                "$set": {
                    "is_current_version": False,
                    "replacement_status": "blocked",
                    "updated_at": now,
                }
            },
        )
        _clear_upload_replacement_claim(
            db=db,
            upload_id=prior_id,
            claim_token=claim_token,
        )
    elif category == "private_media":
        db["uploaded_files"].update_one(
            {"_id": ObjectId(prior_id)},
            {
                "$set": {
                    "is_current_version": False,
                    "superseded_by_upload_id": replacement_id,
                    "pending_replacement_upload_id": None,
                    "replacement_status": "superseded",
                    "replacement_claim_token": None,
                    "replacement_claimed_at": None,
                    "updated_at": now,
                }
            },
        )
        db["uploaded_files"].update_one(
            {"_id": ObjectId(replacement_id)},
            {
                "$set": {
                    "is_current_version": True,
                    "replacement_status": "current",
                    "updated_at": now,
                }
            },
        )
    else:
        # Portrait and verification replacements do not displace the approved
        # current file until their existing review workflow approves them.
        db["uploaded_files"].update_one(
            {"_id": ObjectId(prior_id)},
            {
                "$set": {
                    "pending_replacement_upload_id": replacement_id,
                    "replacement_claim_token": None,
                    "replacement_claimed_at": None,
                    "updated_at": now,
                }
            },
        )
        db["uploaded_files"].update_one(
            {"_id": ObjectId(replacement_id)},
            {
                "$set": {
                    "is_current_version": False,
                    "replacement_status": "pending_review",
                    "updated_at": now,
                }
            },
        )
    refreshed = db["uploaded_files"].find_one({"_id": ObjectId(replacement_id)})
    return refreshed or replacement


def _complete_reviewed_replacement(
    *,
    db: Any,
    upload_record: dict[str, Any],
    approved: bool,
) -> dict[str, Any]:
    replacement_id = _normalize_value(upload_record.get("_id") or upload_record.get("id"))
    prior_id = _normalize_value(upload_record.get("replaces_upload_id"))
    if not prior_id or not ObjectId.is_valid(prior_id) or not ObjectId.is_valid(replacement_id):
        return upload_record
    now = datetime.now(UTC).isoformat()
    if approved:
        db["uploaded_files"].update_one(
            {"_id": ObjectId(prior_id)},
            {
                "$set": {
                    "is_current_version": False,
                    "superseded_by_upload_id": replacement_id,
                    "pending_replacement_upload_id": None,
                    "replacement_status": "superseded",
                    "updated_at": now,
                }
            },
        )
        new_state = {"is_current_version": True, "replacement_status": "current"}
    else:
        db["uploaded_files"].update_one(
            {"_id": ObjectId(prior_id)},
            {
                "$set": {
                    "pending_replacement_upload_id": None,
                    "updated_at": now,
                }
            },
        )
        new_state = {"is_current_version": False, "replacement_status": "rejected"}
    db["uploaded_files"].update_one(
        {"_id": ObjectId(replacement_id)},
        {"$set": {**new_state, "updated_at": now}},
    )
    return db["uploaded_files"].find_one({"_id": ObjectId(replacement_id)}) or upload_record


def _apply_customer_visibility_filter(
    query: dict[str, Any],
    *,
    is_admin: bool,
    current_user: dict[str, Any],
) -> None:
    if is_admin:
        return

    current_user_id = _current_user_id(current_user)
    query["account_access_enabled"] = {"$ne": False}
    query["owner_account_deleted"] = {"$ne": True}
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

    raw_records = list(
        db["uploaded_files"].find(query).sort("created_at", -1).limit(limit)
    )
    records, duplicates_suppressed = _deduplicate_admin_review_records(raw_records)

    return {
        "count": len(records),
        "raw_count": len(raw_records),
        "duplicates_suppressed": duplicates_suppressed,
        "items": [
            _serialize_admin_upload_review(record, db=db)
            for record in records
        ],
    }


@router.post("/member-photo")
async def upload_member_photo(
    family_id: str = Form(...),
    member_id: str = Form(...),
    consent_attested: bool = Form(...),
    authority_attested: bool = Form(...),
    vault_item_id: str = Form(""),
    file: UploadFile = File(...),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
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

    if consent_attested is not True or authority_attested is not True:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Portrait consent and upload authority must both be confirmed.",
        )

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

    _enforce_workspace_upload_limit(context, db=db)
    _enforce_workspace_storage_limit(
        context=context,
        db=db,
        incoming_size_bytes=_upload_size_bytes(file),
    )

    key_hash, fingerprint, replay = _begin_upload_idempotency(
        db=db,
        idempotency_key=idempotency_key,
        operation="member_photo_create",
        current_user=current_user,
        upload=file,
        fields={
            "project_id": _normalize_value(context["project"].get("_id")),
            "family_id": actual_family_id,
            "member_id": member_id,
            "vault_item_id": vault_item_id if isinstance(vault_item_id, str) else "",
        },
    )
    if replay is not None:
        await file.close()
        replay = _resume_replayed_upload(db=db, upload_record=replay)
        if isinstance(vault_item_id, str) and vault_item_id.strip():
            replay = _ensure_upload_vault_linkage(
                db=db,
                upload_record=replay,
                current_user=current_user,
                authorized_project_id=_normalize_value(context["project"].get("_id")),
                requested_vault_item_id=vault_item_id,
                workspace_member_role=_normalize_value(context.get("member_role")),
            )
        _finish_upload_idempotency(db=db, key_hash=key_hash, upload_record=replay)
        return {
            "message": _upload_status_payload(replay)["message"],
            "upload": _public_upload_record(
                replay,
                context=context,
                current_user=current_user,
            ),
            "upload_status": _upload_status_payload(replay),
            "idempotency_replayed": True,
            "member_id": member_id,
            "family_id": actual_family_id,
        }

    try:
        upload_record = await store_member_photo_upload(
            db=db,
            project_id=_normalize_value(context["project"].get("_id")),
            family_id=actual_family_id,
            member_id=member_id,
            upload=file,
            uploaded_by=_actor_label(current_user),
            uploaded_by_user_id=_current_user_id(current_user),
            consent_attested=consent_attested,
            authority_attested=authority_attested,
            vault_item_id=vault_item_id if isinstance(vault_item_id, str) else "",
            idempotency_key_hash=key_hash,
            idempotency_fingerprint=fingerprint,
        )
        upload_record = _scan_and_quarantine_upload(db=db, upload_record=upload_record)
        if isinstance(vault_item_id, str) and vault_item_id.strip():
            upload_record = _ensure_upload_vault_linkage(
                db=db,
                upload_record=upload_record,
                current_user=current_user,
                authorized_project_id=_normalize_value(context["project"].get("_id")),
                requested_vault_item_id=vault_item_id,
                workspace_member_role=_normalize_value(context.get("member_role")),
            )
        _finish_upload_idempotency(
            db=db,
            key_hash=key_hash,
            upload_record=upload_record,
        )
    except Exception:
        _release_upload_idempotency(db=db, key_hash=key_hash)
        raise

    return {
        "message": _upload_status_payload(upload_record)["message"],
        "upload": _public_upload_record(
            upload_record,
            context=context,
            current_user=current_user,
        ),
        "upload_status": _upload_status_payload(upload_record),
        "idempotency_replayed": False,
        "member_id": member_id,
        "family_id": actual_family_id,
    }


@router.post("/verification-evidence")
async def upload_verification_evidence(
    family_id: str = Form(...),
    member_id: str = Form(...),
    verification_type: str = Form(...),
    evidence_kind: str = Form("supporting_family_record"),
    vault_item_id: str = Form(""),
    file: UploadFile = File(...),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
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

    _enforce_workspace_upload_limit(context, db=db)
    _enforce_workspace_storage_limit(
        context=context,
        db=db,
        incoming_size_bytes=_upload_size_bytes(file),
    )

    key_hash, fingerprint, replay = _begin_upload_idempotency(
        db=db,
        idempotency_key=idempotency_key,
        operation="verification_evidence_create",
        current_user=current_user,
        upload=file,
        fields={
            "project_id": _normalize_value(context["project"].get("_id")),
            "family_id": actual_family_id,
            "member_id": member_id,
            "verification_type": normalized_verification_type,
            "evidence_kind": normalized_evidence_kind,
            "vault_item_id": vault_item_id if isinstance(vault_item_id, str) else "",
        },
    )
    if replay is not None:
        await file.close()
        replay = _resume_replayed_upload(db=db, upload_record=replay)
        if isinstance(vault_item_id, str) and vault_item_id.strip():
            replay = _ensure_upload_vault_linkage(
                db=db,
                upload_record=replay,
                current_user=current_user,
                authorized_project_id=_normalize_value(context["project"].get("_id")),
                requested_vault_item_id=vault_item_id,
                workspace_member_role=_normalize_value(context.get("member_role")),
            )
        _finish_upload_idempotency(db=db, key_hash=key_hash, upload_record=replay)
        return {
            "message": _upload_status_payload(replay)["message"],
            "upload": _public_upload_record(
                replay,
                context=context,
                current_user=current_user,
            ),
            "upload_status": _upload_status_payload(replay),
            "idempotency_replayed": True,
            "member_id": member_id,
            "family_id": actual_family_id,
        }

    try:
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
            vault_item_id=vault_item_id if isinstance(vault_item_id, str) else "",
            idempotency_key_hash=key_hash,
            idempotency_fingerprint=fingerprint,
        )
        upload_record = _scan_and_quarantine_upload(db=db, upload_record=upload_record)
        if isinstance(vault_item_id, str) and vault_item_id.strip():
            upload_record = _ensure_upload_vault_linkage(
                db=db,
                upload_record=upload_record,
                current_user=current_user,
                authorized_project_id=_normalize_value(context["project"].get("_id")),
                requested_vault_item_id=vault_item_id,
                workspace_member_role=_normalize_value(context.get("member_role")),
            )
        _finish_upload_idempotency(
            db=db,
            key_hash=key_hash,
            upload_record=upload_record,
        )
    except Exception:
        _release_upload_idempotency(db=db, key_hash=key_hash)
        raise

    return {
        "message": _upload_status_payload(upload_record)["message"],
        "upload": _public_upload_record(
            upload_record,
            context=context,
            current_user=current_user,
        ),
        "upload_status": _upload_status_payload(upload_record),
        "idempotency_replayed": False,
        "member_id": member_id,
        "family_id": actual_family_id,
    }


@router.post("/private-media")
async def upload_private_media(
    family_id: str = Form(""),
    member_id: str = Form(""),
    project_id: str = Form(""),
    asset_type: str = Form(...),
    privacy_scope: str = Form("private_to_owner"),
    vault_scope: str = Form(""),
    vault_item_id: str = Form(""),
    release_state: str = Form("released"),
    reveal_at: str = Form(""),
    consent_attested: bool = Form(...),
    authority_attested: bool = Form(...),
    file: UploadFile = File(...),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    context = require_workspace_capability(
        current_user,
        project_id=project_id if isinstance(project_id, str) else "",
        family_id=family_id,
        member_id=member_id,
        capabilities=VAULT_CAPABILITIES,
        detail="Your active package does not include private Vault access.",
    )
    require_workspace_member_role(
        context,
        allowed_roles=("billing_owner", "co_owner", "family_manager", "contributor"),
        detail="Your role is read-only for uploads.",
    )
    require_workspace_maintenance_write_access(context, feature_name="Vault")

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    if consent_attested is not True or authority_attested is not True:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Vault consent and upload authority must both be confirmed.",
        )

    normalized_asset_type = _canonical_vault_asset_type(asset_type)
    if normalized_asset_type not in PRIVATE_MEDIA_ALLOWED_ASSET_TYPES:
        raise HTTPException(status_code=400, detail="Invalid private media asset type.")

    normalized_privacy_scope = _normalize_visibility_scope(privacy_scope, "private_to_owner")
    if normalized_privacy_scope not in PRIVATE_MEDIA_ALLOWED_PRIVACY_SCOPES:
        raise HTTPException(status_code=400, detail="Invalid private media privacy scope.")

    normalized_vault_scope, _required_capability = _resolve_vault_scope_for_create(
        context=context,
        requested_scope=vault_scope if isinstance(vault_scope, str) else "",
    )
    normalized_release_state, normalized_reveal_at = _resolve_upload_release_fields(
        context=context,
        release_state=release_state if isinstance(release_state, str) else "released",
        reveal_at=reveal_at if isinstance(reveal_at, str) else "",
    )
    _enforce_allowed_asset_type(context=context, asset_type=normalized_asset_type)
    if normalized_asset_type == "vault_photo":
        _validate_upload_file(
            file,
            allowed_content_types=PHOTO_ALLOWED_CONTENT_TYPES,
            allowed_extensions=PHOTO_ALLOWED_EXTENSIONS,
            max_bytes=PHOTO_MAX_BYTES,
            label="Vault photo",
        )
    elif normalized_asset_type == "vault_document":
        _validate_upload_file(
            file,
            allowed_content_types=EVIDENCE_ALLOWED_CONTENT_TYPES,
            allowed_extensions=EVIDENCE_ALLOWED_EXTENSIONS,
            max_bytes=EVIDENCE_MAX_BYTES,
            label="Vault document",
        )
    else:
        _validate_upload_file(
            file,
            allowed_content_types=PRIVATE_MEDIA_ALLOWED_CONTENT_TYPES,
            allowed_extensions=PRIVATE_MEDIA_ALLOWED_EXTENSIONS,
            max_bytes=EVIDENCE_MAX_BYTES,
            label="private media",
        )

    member = context.get("member") or {}
    actual_member_id = _normalize_value(member.get("_id")) or _normalize_value(member_id)
    actual_family_id = _normalize_value(member.get("family_id")) or _normalize_value(
        (context.get("family") or {}).get("_id")
    )
    if member and _normalize_value(family_id) != actual_family_id:
        raise HTTPException(status_code=400, detail="family_id does not match the selected member.")
    if normalized_vault_scope == "household" and not actual_family_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Household Vault uploads require a household.",
        )
    if normalized_privacy_scope == "household_private" and normalized_vault_scope != "household":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="household_private visibility is available only in a household Vault.",
        )
    share_with_linked_families = normalized_privacy_scope == "linked_family_shared"
    if normalized_vault_scope == "linked_family" and not share_with_linked_families:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A linked-family Vault upload must use linked_family_shared visibility.",
        )
    if share_with_linked_families and normalized_vault_scope != "linked_family":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="linked_family_shared visibility requires the linked-family Vault scope.",
        )
    if normalized_vault_scope == "linked_family":
        if not context.get("is_admin") and not bool(
            (context.get("resolved_entitlements") or {}).get("can_link_households")
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your active package does not include linked-household access.",
            )
        if not actual_family_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Linked-family Vault uploads require a household.",
            )
        try:
            linked_family_ids = list_linked_family_ids(actual_family_id)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Linked-family status could not be verified.",
            ) from exc
        if len({value for value in linked_family_ids if _normalize_value(value)}) < 2:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="An accepted household link is required for linked-family Vault uploads.",
            )

    _enforce_workspace_upload_limit(context, db=db)
    _enforce_workspace_storage_limit(
        context=context,
        db=db,
        incoming_size_bytes=_upload_size_bytes(file),
    )

    actual_project_id = _normalize_value((context.get("project") or {}).get("_id"))
    normalized_vault_item_id = vault_item_id if isinstance(vault_item_id, str) else ""
    key_hash, fingerprint, replay = _begin_upload_idempotency(
        db=db,
        idempotency_key=idempotency_key,
        operation="private_vault_create",
        current_user=current_user,
        upload=file,
        fields={
            "project_id": actual_project_id,
            "family_id": actual_family_id,
            "member_id": actual_member_id,
            "asset_type": normalized_asset_type,
            "privacy_scope": normalized_privacy_scope,
            "vault_scope": normalized_vault_scope,
            "vault_item_id": normalized_vault_item_id,
            "share_with_linked_families": share_with_linked_families,
            "release_state": normalized_release_state,
            "reveal_at": normalized_reveal_at or "",
        },
    )
    if replay is not None:
        await file.close()
        replay = _resume_replayed_upload(db=db, upload_record=replay)
        replay = _ensure_upload_vault_linkage(
            db=db,
            upload_record=replay,
            current_user=current_user,
            authorized_project_id=actual_project_id,
            requested_vault_item_id=normalized_vault_item_id,
            workspace_member_role=_normalize_value(context.get("member_role")),
        )
        _finish_upload_idempotency(db=db, key_hash=key_hash, upload_record=replay)
        return {
            "message": _upload_status_payload(replay)["message"],
            "upload": _public_upload_record(
                replay,
                context=context,
                current_user=current_user,
            ),
            "upload_status": _upload_status_payload(replay),
            "idempotency_replayed": True,
            "member_id": actual_member_id or None,
            "family_id": actual_family_id or None,
        }

    try:
        upload_record = await store_private_media_upload(
            db=db,
            project_id=actual_project_id,
            family_id=actual_family_id,
            member_id=actual_member_id,
            asset_type=normalized_asset_type,
            privacy_scope=normalized_privacy_scope,
            vault_scope=normalized_vault_scope,
            consent_attested=consent_attested,
            authority_attested=authority_attested,
            vault_item_id=normalized_vault_item_id,
            upload=file,
            uploaded_by=_actor_label(current_user),
            uploaded_by_user_id=_current_user_id(current_user),
            idempotency_key_hash=key_hash,
            idempotency_fingerprint=fingerprint,
            release_state=normalized_release_state,
            reveal_at=normalized_reveal_at,
            share_with_linked_families=share_with_linked_families,
        )
        upload_record = _scan_and_quarantine_upload(db=db, upload_record=upload_record)
        upload_record = _ensure_upload_vault_linkage(
            db=db,
            upload_record=upload_record,
            current_user=current_user,
            authorized_project_id=actual_project_id,
            requested_vault_item_id=normalized_vault_item_id,
            workspace_member_role=_normalize_value(context.get("member_role")),
        )
        _finish_upload_idempotency(
            db=db,
            key_hash=key_hash,
            upload_record=upload_record,
        )
    except Exception:
        _release_upload_idempotency(db=db, key_hash=key_hash)
        raise
    return {
        "message": _upload_status_payload(upload_record)["message"],
        "upload": _public_upload_record(
            upload_record,
            context=context,
            current_user=current_user,
        ),
        "upload_status": _upload_status_payload(upload_record),
        "idempotency_replayed": False,
        "member_id": actual_member_id or None,
        "family_id": actual_family_id or None,
    }


@router.get("/member/{member_id}")
def list_member_uploads(
    member_id: str,
    category: Optional[str] = Query(default=None),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    normalized_category = _validate_category_filter(category)
    context = _resolve_upload_list_context(
        current_user=current_user,
        member_id=member_id,
        category=normalized_category or "",
        detail="Your active package does not include upload access.",
    )

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    member = context["member"]
    family = context["family"]
    project = context["project"]

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

    candidates = list(db["uploaded_files"].find(query).sort("created_at", -1))
    records = [
        record
        for record in candidates
        if _can_list_upload_record(
            upload_record=record,
            context=context,
            current_user=current_user,
        )
    ]
    return {
        "member_id": str(member.get("_id")),
        "count": len(records),
        "uploads": _serialize_uploads(
            records,
            context=context,
            current_user=current_user,
        ),
    }


@router.get("/family/{family_id}")
def list_family_uploads(
    family_id: str,
    category: Optional[str] = Query(default=None),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    normalized_category = _validate_category_filter(category)
    context = _resolve_upload_list_context(
        current_user=current_user,
        family_id=family_id,
        category=normalized_category or "",
        detail="Your active package does not include upload access.",
    )

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    family = context["family"]
    project = context["project"]
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

    candidates = list(db["uploaded_files"].find(query).sort("created_at", -1))
    records = [
        record
        for record in candidates
        if _can_list_upload_record(
            upload_record=record,
            context=context,
            current_user=current_user,
        )
    ]
    return {
        "family_id": _normalize_value((family or {}).get("_id")),
        "count": len(records),
        "uploads": _serialize_uploads(
            records,
            context=context,
            current_user=current_user,
        ),
    }


@router.get("/vault/family/{family_id}")
def list_family_vault_items(
    family_id: str,
    include_linked_families: bool = Query(default=False),
    vault_scope: Optional[str] = Query(default=None),
    visibility_scope: Optional[str] = Query(default=None),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    context = _resolve_upload_list_context(
        current_user=current_user,
        family_id=family_id,
        category="private_media",
        detail="Your active package does not include private Vault access.",
    )

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    base_family_id = _normalize_value((context.get("family") or {}).get("_id"))
    family_ids = [base_family_id]
    if include_linked_families:
        entitlements = context.get("resolved_entitlements") or {}
        has_link_capability = bool(context.get("is_admin")) or bool(
            entitlements.get("can_link_households")
            and entitlements.get(LINKED_FAMILY_VAULT_CAPABILITY)
        )
        if not has_link_capability:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your active package does not include linked family vault access.",
            )
        family_ids = list_linked_family_ids(base_family_id)

    query: dict[str, Any] = {
        "family_id": {"$in": [fid for fid in family_ids if fid]},
        "category": "private_media",
        "account_access_enabled": {"$ne": False},
        "owner_account_deleted": {"$ne": True},
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

    candidates = list(db["uploaded_files"].find(query).sort("created_at", -1))
    records: list[dict[str, Any]] = []
    for record in candidates:
        if not _can_list_upload_record(
            upload_record=record,
            context=context,
            current_user=current_user,
        ):
            continue
        record_family_id = _normalize_value(record.get("family_id"))
        linked_record = bool(record_family_id and record_family_id != base_family_id)
        if linked_record and not _is_upload_owner(record, current_user):
            if (
                not bool(record.get("share_with_linked_families"))
                or _upload_classification(record) != "linked_family_shared"
                or _canonical_vault_scope(record.get("vault_scope")) != "linked_family"
            ):
                continue
        records.append(record)
    return {
        "family_id": base_family_id,
        "linked_family_ids": family_ids,
        "count": len(records),
        "items": _serialize_uploads(
            records,
            context=context,
            current_user=current_user,
        ),
    }


@router.get("/vault/project/{project_id}")
def list_project_vault_items(
    project_id: str,
    member_id: str = Query(default=""),
    category: Optional[str] = Query(default=None),
    vault_scope: Optional[str] = Query(default=None),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """List customer-visible Vault uploads without requiring household ids."""

    normalized_category = _validate_category_filter(category)
    context = _resolve_upload_list_context(
        current_user=current_user,
        project_id=project_id,
        member_id=_normalize_value(member_id),
        category=normalized_category or "",
        detail="Your active package does not include access to these Vault uploads.",
    )
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    canonical_project_id = _normalize_value((context.get("project") or {}).get("_id"))
    query: dict[str, Any] = {"project_id": canonical_project_id}
    if normalized_category:
        query["category"] = normalized_category
    normalized_member_id = _normalize_value(member_id)
    if normalized_member_id:
        query["member_id"] = normalized_member_id
    if vault_scope is not None:
        normalized_scope = _normalize_vault_scope(vault_scope, default="")
        if not normalized_scope:
            raise HTTPException(status_code=400, detail="Invalid Vault scope filter.")
        query["vault_scope"] = normalized_scope
    _apply_customer_visibility_filter(
        query,
        is_admin=bool(context.get("is_admin")),
        current_user=current_user,
    )
    candidates = list(db["uploaded_files"].find(query).sort("created_at", -1))
    records = [
        record
        for record in candidates
        if _can_list_upload_record(
            upload_record=record,
            context=context,
            current_user=current_user,
        )
    ]
    return {
        "project_id": canonical_project_id,
        "member_id": normalized_member_id or None,
        "count": len(records),
        "items": _serialize_uploads(
            records,
            context=context,
            current_user=current_user,
        ),
    }


@router.get("/{upload_id}/versions")
def list_upload_versions(
    upload_id: str,
    viewer_project_id: str = Query(default=""),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")
    normalized_viewer_project_id = (
        _normalize_value(viewer_project_id)
        if isinstance(viewer_project_id, str)
        else ""
    )
    linked_viewer = bool(normalized_viewer_project_id)
    if linked_viewer:
        upload_record, context = _require_linked_vault_upload_access(
            upload_id,
            normalized_viewer_project_id,
            db,
            current_user,
            require_current=True,
        )
    else:
        upload_record, context = _require_upload_access(
            upload_id,
            db,
            current_user,
            detail="Your active package does not include access to this upload history.",
        )
    root_upload_id = _normalize_value(
        upload_record.get("version_group_id") or upload_record.get("_id")
    )
    candidates = list(
        db["uploaded_files"].find(
            {
                "$or": [
                    {"version_group_id": root_upload_id},
                    {"_id": ObjectId(root_upload_id)}
                    if ObjectId.is_valid(root_upload_id)
                    else {"version_group_id": root_upload_id},
                ]
            }
        ).sort("version", -1)
    )
    if linked_viewer:
        records = []
        for record in candidates:
            candidate_id = _normalize_value(record.get("_id") or record.get("id"))
            if not candidate_id:
                continue
            try:
                _require_linked_vault_upload_access(
                    candidate_id,
                    normalized_viewer_project_id,
                    db,
                    current_user,
                    require_current=True,
                )
            except HTTPException:
                continue
            records.append(record)
    else:
        records = [
            record
            for record in candidates
            if (
                (
                    _context_has_any_capability(
                        context,
                        _upload_category_capabilities(record),
                    )
                    or _has_retained_upload_lifecycle_access(
                        upload_record=record,
                        context=context,
                        current_user=current_user,
                    )
                )
                and _can_access_upload_record(
                    upload_record=record,
                    context=context,
                    current_user=current_user,
                )
            )
        ]
    return {
        "upload_id": upload_id,
        "root_upload_id": root_upload_id,
        "count": len(records),
        "versions": _serialize_uploads(
            records,
            context=context,
            current_user=current_user,
        ),
    }


@router.post("/{upload_id}/replace")
async def replace_upload(
    upload_id: str,
    file: UploadFile = File(...),
    consent_attested: bool | None = Form(None),
    authority_attested: bool | None = Form(None),
    privacy_scope: str = Form(""),
    vault_item_id: str = Form(""),
    release_state: str = Form(""),
    reveal_at: str = Form(""),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")
    prior_upload, context = _require_upload_management_access(
        upload_id,
        db,
        current_user,
        action="replace",
    )
    category = _normalize_value(prior_upload.get("category")).lower()
    if category == "private_media":
        require_workspace_maintenance_write_access(context, feature_name="Vault")
    capabilities = _upload_category_capabilities(prior_upload)
    if not capabilities or not _context_has_any_capability(context, capabilities):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your active package does not include replacement for this upload type.",
        )
    require_workspace_member_role(
        context,
        allowed_roles=("billing_owner", "co_owner", "family_manager", "contributor"),
        detail="Your role is read-only for uploads.",
    )
    if category in {"member_photo", "private_media"} and (
        consent_attested is not True or authority_attested is not True
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Consent and upload authority must both be confirmed for this replacement.",
        )
    _validate_replacement_file(prior_upload, file)
    if category == "private_media":
        _enforce_allowed_asset_type(
            context=context,
            asset_type=_canonical_vault_asset_type(prior_upload.get("asset_type")),
        )

    requested_privacy = privacy_scope if isinstance(privacy_scope, str) else ""
    normalized_privacy_scope = _normalize_visibility_scope(
        requested_privacy,
        _normalize_value(
            prior_upload.get("privacy_classification")
            or prior_upload.get("privacy_scope")
            or prior_upload.get("visibility_scope")
        )
        or "private_to_owner",
    )
    existing_privacy_scope = _upload_classification(prior_upload)
    if requested_privacy and normalized_privacy_scope != existing_privacy_scope:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Change Vault privacy through the privacy endpoint before replacing its file.",
        )
    if category == "private_media" and normalized_privacy_scope not in PRIVATE_MEDIA_ALLOWED_PRIVACY_SCOPES:
        raise HTTPException(status_code=400, detail="Invalid private media privacy scope.")

    existing_vault_item_id = _normalize_value(prior_upload.get("vault_item_id"))
    requested_vault_item_id = (
        _normalize_value(vault_item_id) if isinstance(vault_item_id, str) else ""
    )
    if (
        existing_vault_item_id
        and requested_vault_item_id
        and existing_vault_item_id != requested_vault_item_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A replacement must remain linked to the same Vault item.",
        )
    effective_vault_item_id = existing_vault_item_id or requested_vault_item_id

    effective_release_state = _normalize_value(prior_upload.get("release_state")) or "released"
    effective_reveal_at = _normalize_value(prior_upload.get("reveal_at")) or None
    if category == "private_media" and (
        (isinstance(release_state, str) and release_state.strip())
        or (isinstance(reveal_at, str) and reveal_at.strip())
    ):
        effective_release_state, effective_reveal_at = _resolve_upload_release_fields(
            context=context,
            release_state=release_state,
            reveal_at=reveal_at,
        )

    project_id = _normalize_value(prior_upload.get("project_id"))
    family_id = _normalize_value(prior_upload.get("family_id"))
    member_id = _normalize_value(prior_upload.get("member_id"))
    # A replacement creates a physical version, not a new logical customer
    # asset, so it must not consume another upload-count entitlement.
    _enforce_workspace_storage_limit(
        context=context,
        db=db,
        incoming_size_bytes=_upload_size_bytes(file),
    )
    key_hash, fingerprint, replay = _begin_upload_idempotency(
        db=db,
        idempotency_key=idempotency_key,
        operation=f"replace:{upload_id}",
        current_user=current_user,
        upload=file,
        fields={
            "upload_id": upload_id,
            "privacy_scope": normalized_privacy_scope,
            "vault_item_id": effective_vault_item_id,
            "release_state": effective_release_state,
            "reveal_at": effective_reveal_at or "",
        },
    )
    if replay is not None:
        await file.close()
        replay = _resume_replayed_upload(db=db, upload_record=replay)
        if category == "private_media" and _replacement_is_storage_ready(replay):
            replay = _ensure_upload_vault_linkage(
                db=db,
                upload_record=replay,
                current_user=current_user,
                authorized_project_id=project_id,
                requested_vault_item_id=effective_vault_item_id,
                workspace_member_role=_normalize_value(context.get("member_role")),
            )
        replay = _apply_replacement_state(
            db=db,
            prior_upload=prior_upload,
            replacement=replay,
        )
        response_status = _upload_status_payload(replay)
        public_replay = _public_upload_record(
            replay,
            context=context,
            current_user=current_user,
        )
        _finish_upload_idempotency(db=db, key_hash=key_hash, upload_record=replay)
        return {
            "message": response_status["message"],
            "replacement": public_replay,
            "upload": public_replay,
            "upload_status": response_status,
            "idempotency_replayed": True,
        }

    if not bool(prior_upload.get("is_current_version", True)) or _normalize_value(
        prior_upload.get("superseded_by_upload_id")
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only the current upload version can be replaced.",
        )
    if _normalize_value(prior_upload.get("pending_replacement_upload_id")):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This upload already has a replacement awaiting review.",
        )

    version_group_id = _normalize_value(
        prior_upload.get("version_group_id") or prior_upload.get("_id")
    )
    next_version = max(_as_int(prior_upload.get("version"), 1), 1) + 1
    claim_token = f"replace_{secrets.token_hex(16)}"
    _claim_upload_replacement(
        db=db,
        upload_record=prior_upload,
        claim_token=claim_token,
    )
    try:
        common_fields = {
            "db": db,
            "project_id": project_id,
            "family_id": family_id,
            "member_id": member_id,
            "upload": file,
            "uploaded_by": _actor_label(current_user),
            "uploaded_by_user_id": _current_user_id(current_user),
            "vault_item_id": effective_vault_item_id,
            "version": next_version,
            "version_group_id": version_group_id,
            "replaces_upload_id": upload_id,
            "idempotency_key_hash": key_hash,
            "idempotency_fingerprint": fingerprint,
        }
        if category == "member_photo":
            replacement = await store_member_photo_upload(
                **common_fields,
                consent_attested=True,
                authority_attested=True,
            )
        elif category == "verification_evidence":
            replacement = await store_verification_evidence_upload(
                **common_fields,
                verification_type=_normalize_value(prior_upload.get("verification_type")),
                evidence_kind=_normalize_value(prior_upload.get("evidence_kind"))
                or "supporting_family_record",
            )
        elif category == "private_media":
            replacement = await store_private_media_upload(
                **common_fields,
                asset_type=_canonical_vault_asset_type(prior_upload.get("asset_type")),
                privacy_scope=normalized_privacy_scope,
                vault_scope=_canonical_vault_scope(prior_upload.get("vault_scope")) or "personal",
                consent_attested=True,
                authority_attested=True,
                release_state=effective_release_state,
                reveal_at=effective_reveal_at,
                share_with_linked_families=bool(
                    prior_upload.get("share_with_linked_families")
                ),
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported replacement category.")
        replacement = _scan_and_quarantine_upload(db=db, upload_record=replacement)
        if category == "private_media" and _replacement_is_storage_ready(replacement):
            replacement = _ensure_upload_vault_linkage(
                db=db,
                upload_record=replacement,
                current_user=current_user,
                authorized_project_id=project_id,
                requested_vault_item_id=effective_vault_item_id,
                workspace_member_role=_normalize_value(context.get("member_role")),
            )
        replacement = _apply_replacement_state(
            db=db,
            prior_upload=prior_upload,
            replacement=replacement,
            claim_token=claim_token,
        )
        _finish_upload_idempotency(
            db=db,
            key_hash=key_hash,
            upload_record=replacement,
        )
    except Exception:
        _clear_upload_replacement_claim(
            db=db,
            upload_id=upload_id,
            claim_token=claim_token,
        )
        _release_upload_idempotency(db=db, key_hash=key_hash)
        raise

    response_status = _upload_status_payload(replacement)
    public_replacement = _public_upload_record(
        replacement,
        context=context,
        current_user=current_user,
    )
    return {
        "message": response_status["message"],
        "replacement": public_replacement,
        "upload": public_replacement,
        "upload_status": response_status,
        "idempotency_replayed": False,
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
        action="change privacy for",
    )

    current_scope = _normalize_visibility_scope(upload_record.get("visibility_scope"), "private")
    visibility_scope = (
        _normalize_visibility_scope(payload.visibility_scope, current_scope)
        if payload.visibility_scope is not None
        else current_scope
    )
    category = _normalize_value(upload_record.get("category")).lower()
    if category == "private_media":
        require_workspace_maintenance_write_access(context, feature_name="Vault")
    if category == "verification_evidence":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verification evidence privacy is fixed to its owner-only review policy.",
        )
    if category == "private_media" and not _is_upload_owner(upload_record, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Vault item owner can change its privacy or scope.",
        )
    if not context.get("is_admin"):
        if category == "member_photo" and visibility_scope not in {
            "private_to_owner",
            "private_to_owner_and_co_owner",
            "household_private",
            "minor_protected",
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Portrait privacy must remain owner, co-owner, household, or minor protected.",
            )
        if category == "private_media" and visibility_scope not in PRIVATE_MEDIA_ALLOWED_PRIVACY_SCOPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid privacy scope for this Vault file.",
            )
        if category not in {"member_photo", "private_media", "verification_evidence"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This upload category does not allow customer privacy changes.",
            )
    flag_defaults = _visibility_flags(visibility_scope)
    customer_visible = flag_defaults["customer_visible"]
    internal_only = flag_defaults["internal_only"]
    share_with_linked = flag_defaults["share_with_linked_families"]

    current_vault_scope = _normalize_vault_scope(upload_record.get("vault_scope"), "personal")
    next_vault_scope = (
        _normalize_vault_scope(payload.vault_scope, current_vault_scope)
        if payload.vault_scope is not None
        else current_vault_scope
    )

    if not context.get("is_admin") and (
        payload.customer_visible is not None or payload.internal_only is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer visibility flags are derived from the selected privacy scope.",
        )
    if context.get("is_admin"):
        if payload.customer_visible is not None:
            customer_visible = bool(payload.customer_visible)
        if payload.internal_only is not None:
            internal_only = bool(payload.internal_only)
        if payload.share_with_linked_families is not None:
            share_with_linked = bool(payload.share_with_linked_families)
    elif payload.share_with_linked_families is not None:
        share_with_linked = bool(payload.share_with_linked_families)

    if payload.vault_scope is not None and category != "private_media" and not context.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vault scope can be changed only for Vault media uploads.",
        )
    next_capability = VAULT_SCOPE_CAPABILITY.get(next_vault_scope)
    if (
        category == "private_media"
        and next_capability
        and not context.get("is_admin")
        and not bool((context.get("resolved_entitlements") or {}).get(next_capability))
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your active package does not include the selected Vault scope.",
        )
    canonical_next_vault_scope = _canonical_vault_scope(next_vault_scope) or next_vault_scope
    if visibility_scope == "household_private" and canonical_next_vault_scope != "household":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="household_private visibility requires a household Vault.",
        )
    if visibility_scope == "linked_family_shared":
        has_link_entitlement = bool(context.get("is_admin")) or bool(
            (context.get("resolved_entitlements") or {}).get("can_link_households")
        )
        family_id = _normalize_value(upload_record.get("family_id"))
        try:
            linked_family_ids = list_linked_family_ids(family_id) if family_id else []
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Linked-family status could not be verified.",
            ) from exc
        has_accepted_link = len(
            {value for value in linked_family_ids if _normalize_value(value)}
        ) >= 2
        if (
            not has_link_entitlement
            or not share_with_linked
            or canonical_next_vault_scope != "linked_family"
            or not has_accepted_link
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Linked-family sharing requires its Vault scope, entitlement, explicit sharing, and an accepted link.",
            )
    elif share_with_linked and not context.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Linked-family sharing can be enabled only with linked_family_shared visibility.",
        )

    if internal_only:
        customer_visible = False
    next_classification = visibility_scope
    if payload.privacy_classification is not None:
        requested_classification = _normalize_privacy_classification(
            payload.privacy_classification,
            fallback=next_classification,
        )
        if not context.get("is_admin") and requested_classification != next_classification:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="privacy_classification must match visibility_scope.",
            )
        if context.get("is_admin"):
            next_classification = requested_classification

    now = datetime.now(UTC).isoformat()
    before = {
        "vault_scope": current_vault_scope,
        "visibility_scope": current_scope,
        "privacy_classification": _upload_classification(upload_record),
        "share_with_linked_families": bool(upload_record.get("share_with_linked_families")),
    }
    vault_rollback = _sync_linked_vault_item_privacy(
        upload_record=upload_record,
        current_user=current_user,
        next_vault_scope=next_vault_scope,
        next_privacy_classification=next_classification,
    )
    try:
        result = db["uploaded_files"].update_one(
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
                    "privacy_scope": next_classification,
                    "updated_at": now,
                }
            },
        )
        if getattr(result, "matched_count", 0) != 1:
            raise RuntimeError("upload_privacy_update_missing")
    except Exception as exc:
        try:
            _rollback_linked_vault_item_privacy(
                rollback=vault_rollback,
                upload_record=upload_record,
                current_user=current_user,
            )
        except Exception as rollback_exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Upload privacy failed and Vault rollback requires reconciliation.",
            ) from rollback_exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upload privacy was not changed; linked Vault policy was rolled back.",
        ) from exc
    updated = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)}) or upload_record
    actor = _actor_audit_identity(current_user)
    try:
        write_audit_log(
            actor_user_id=actor["user_id"],
            actor_email=actor["email"],
            actor_name=actor["name"],
            action="uploads.privacy_changed",
            target_type="upload",
            target_id=upload_id,
            before=before,
            after={
                "vault_scope": next_vault_scope,
                "visibility_scope": visibility_scope,
                "privacy_classification": next_classification,
                "share_with_linked_families": share_with_linked,
            },
            context={"project_id": _normalize_value((context.get("project") or {}).get("_id"))},
        )
    except Exception:
        pass
    return {
        "upload": _public_upload_record(
            updated,
            context=context,
            current_user=current_user,
        ),
        "workspace_project_id": _normalize_value((context.get("project") or {}).get("_id")) or None,
    }


@router.post("/{upload_id}/cinematic-approval")
def update_upload_cinematic_approval(
    upload_id: str,
    payload: UploadCinematicApprovalPayload,
    current_user: dict[str, Any] = Depends(
        require_permission("uploads.admin.review")
    ),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    upload_record, context = _require_upload_management_access(upload_id, db, current_user)
    if _normalize_value(upload_record.get("category")) != "member_photo":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only member portraits can be approved for cinematic placement.",
        )
    approving = bool(payload.approved_for_cinematic)
    if approving and (
        _normalize_value(upload_record.get("scan_status")).lower() != "clean"
        or bool(upload_record.get("quarantined"))
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Portrait must pass malware scanning before master approval.",
        )
    if approving and not _upload_has_durable_private_storage(upload_record):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Portrait must be stored in durable private storage before master approval.",
        )
    if approving and _normalize_value(upload_record.get("deletion_status")).lower() in {
        "pending",
        "failed",
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Portrait deletion is pending and cannot be approved.",
        )
    if approving and not (
        bool(upload_record.get("consent_attested"))
        and bool(upload_record.get("authority_attested"))
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Portrait is missing the required consent and authority attestations.",
        )
    verification_status = (
        _normalize_value(payload.verification_status).lower()
        or ("approved" if approving else "rejected")
    )
    consent_status = (
        _normalize_value(payload.consent_status).lower()
        or ("approved" if approving else "rejected")
    )
    if approving and (
        verification_status != "approved" or consent_status != "approved"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cinematic approval requires approved verification and consent decisions.",
        )
    now = datetime.now(UTC).isoformat()
    db["uploaded_files"].update_one(
        {"_id": ObjectId(upload_id)},
        {
            "$set": {
                "approved_for_cinematic": approving,
                "approved_by": _actor_label(current_user),
                "approved_by_user_id": _current_user_id(current_user),
                "verification_status": verification_status,
                "consent_status": consent_status,
                "master_review_status": "approved" if approving else "rejected",
                "master_reviewed_at": now,
                "master_review_notes": _normalize_value(payload.review_notes),
                "updated_at": now,
            }
        },
    )
    updated = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)}) or upload_record
    updated = _complete_reviewed_replacement(
        db=db,
        upload_record=updated,
        approved=approving,
    )
    member_id = _normalize_value(upload_record.get("member_id"))
    if member_id and ObjectId.is_valid(member_id):
        member_update: dict[str, Any] = {
            "pending_photo_upload_id": None,
            "photo_submission_status": "approved" if approving else "rejected",
            "updated_at": now,
        }
        if approving:
            member_update.update(
                {
                    "approved_photo_upload_id": upload_id,
                    "photo_upload_id": upload_id,
                    "photo_path": upload_record.get("relative_path"),
                    "photo_original_filename": upload_record.get("original_filename"),
                    "photo_content_type": upload_record.get("content_type"),
                    "photo_size_bytes": upload_record.get("size_bytes"),
                    "portrait_approved_at": now,
                }
            )
        else:
            member = db["family_members"].find_one({"_id": ObjectId(member_id)}) or {}
            if _normalize_value(member.get("approved_photo_upload_id")) == upload_id:
                member_update.update(
                    {
                        "approved_photo_upload_id": None,
                        "photo_upload_id": None,
                        "photo_path": None,
                        "portrait_approved_at": None,
                    }
                )
        db["family_members"].update_one(
            {"_id": ObjectId(member_id)},
            {"$set": member_update},
        )
    return {
        "upload": _public_upload_record(
            updated,
            context=context,
            current_user=current_user,
        )
    }


@router.post("/{upload_id}/verification-review")
def update_upload_verification_review(
    upload_id: str,
    payload: UploadVerificationReviewPayload,
    current_user: dict[str, Any] = Depends(
        require_permission("uploads.admin.review")
    ),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    upload_record, context = _require_upload_management_access(
        upload_id,
        db,
        current_user,
    )
    if _normalize_value(upload_record.get("category")) != "verification_evidence":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only verification evidence can be decided through this review.",
        )

    decision = _normalize_value(payload.decision).lower()
    if decision == "approved" and (
        _normalize_value(upload_record.get("scan_status")).lower() != "clean"
        or bool(upload_record.get("quarantined"))
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Verification evidence must pass malware scanning before approval.",
        )
    if decision == "approved" and not _upload_has_durable_private_storage(upload_record):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Verification evidence must be stored in durable private storage "
                "before approval."
            ),
        )
    if decision == "approved" and _normalize_value(
        upload_record.get("deletion_status")
    ).lower() in {"pending", "failed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Verification evidence deletion is pending and cannot be approved.",
        )

    now = datetime.now(UTC).isoformat()
    db["uploaded_files"].update_one(
        {"_id": ObjectId(upload_id)},
        {
            "$set": {
                "verification_status": decision,
                "verified_by": _actor_label(current_user),
                "verified_by_user_id": _current_user_id(current_user),
                "verified_at": now,
                "verification_review_notes": _normalize_value(
                    payload.review_notes
                ),
                "updated_at": now,
            }
        },
    )
    updated = db["uploaded_files"].find_one(
        {"_id": ObjectId(upload_id)}
    ) or upload_record
    updated = _complete_reviewed_replacement(
        db=db,
        upload_record=updated,
        approved=decision == "approved",
    )
    return {
        "upload": _public_upload_record(
            updated,
            context=context,
            current_user=current_user,
        )
    }


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
        "scan_status": "clean",
        "quarantined": {"$ne": True},
        "approved_for_cinematic": True,
        "verification_status": "approved",
        "consent_status": "approved",
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
            link_status=_context_link_status(context),
            is_owner=user_id == _normalize_value(record.get("uploaded_by_user_id")),
        )
    ]
    return {"family_id": family_id, "count": len(visible), "items": _serialize_uploads(visible)}


@router.post("/{upload_id}/portrait-attestations")
def attest_existing_portrait_upload(
    upload_id: str,
    payload: UploadPortraitAttestationPayload,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    if not payload.consent_attested or not payload.authority_attested:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Portrait consent and upload authority must both be confirmed.",
        )
    db = get_database()
    upload_record, context = _require_upload_management_access(
        upload_id,
        db,
        current_user,
    )
    if _normalize_value(upload_record.get("category")) != "member_photo":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attestations can be recorded only for a member portrait.",
        )

    current_user_id = _current_user_id(current_user)
    uploaded_by_user_id = _normalize_value(upload_record.get("uploaded_by_user_id"))
    project_owner_user_id = _normalize_value(
        (context.get("project") or {}).get("owner_user_id")
    )
    if context.get("is_admin") and current_user_id not in {
        uploaded_by_user_id,
        project_owner_user_id,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "An administrator cannot provide customer consent or upload-authority "
                "attestations on the customer's behalf."
            ),
        )

    now = datetime.now(UTC).isoformat()
    before = {
        "consent_attested": bool(upload_record.get("consent_attested")),
        "authority_attested": bool(upload_record.get("authority_attested")),
    }
    db["uploaded_files"].update_one(
        {"_id": ObjectId(upload_id)},
        {
            "$set": {
                "consent_attested": True,
                "authority_attested": True,
                "consent_attested_at": now,
                "consent_attested_by_user_id": current_user_id,
                "authority_attested_at": now,
                "authority_attested_by_user_id": current_user_id,
                "updated_at": now,
            }
        },
    )
    actor = _actor_audit_identity(current_user)
    write_audit_log(
        actor_user_id=actor["user_id"],
        actor_email=actor["email"],
        actor_name=actor["name"],
        action="uploads.portrait_attestations_recorded",
        target_type="upload",
        target_id=upload_id,
        before=before,
        after={"consent_attested": True, "authority_attested": True},
        context={"surface": "customer_portrait_upload"},
    )
    updated = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)}) or upload_record
    return {"upload": _public_upload_record(updated)}


@router.get("/{upload_id}/admin-preview")
def preview_upload_for_admin_review(
    upload_id: str,
    current_user: dict[str, Any] = Depends(
        require_permission("uploads.admin.review")
    ),
):
    db = get_database()
    upload_record, _context = _require_upload_management_access(
        upload_id,
        db,
        current_user,
    )
    if _normalize_value(upload_record.get("category")).lower() not in {
        "member_photo",
        "verification_evidence",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative preview is limited to portrait and verification review files.",
        )
    if _upload_scan_blocks_download(upload_record):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run the security scan and obtain a clean verdict before previewing this file.",
        )
    if not _upload_has_durable_private_storage(upload_record):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Private storage migration must complete before preview.",
        )

    actor = _actor_audit_identity(current_user)
    try:
        write_audit_log(
            actor_user_id=actor["user_id"],
            actor_email=actor["email"],
            actor_name=actor["name"],
            action="uploads.admin.preview_accessed",
            target_type="upload",
            target_id=upload_id,
            before=None,
            after={"access": "inline_preview"},
            context={
                "surface": "admin_upload_review",
                "category": _normalize_value(upload_record.get("category")),
                "project_id": _normalize_value(upload_record.get("project_id")) or None,
                "vault_item_id": _normalize_value(upload_record.get("vault_item_id")) or None,
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Preview audit checkpoint failed; the file was not streamed.",
        ) from exc

    content_type = _normalize_value(upload_record.get("content_type")) or "application/octet-stream"
    filename = Path(
        _normalize_value(upload_record.get("original_filename")) or "review-file"
    ).name.replace('"', "")
    if _normalize_value(upload_record.get("storage_provider")).lower() == "r2":
        storage_key = _normalize_value(upload_record.get("storage_key"))
        try:
            body = download_private_bytes(
                key=storage_key,
                max_bytes=_upload_read_limit(upload_record),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Private object storage is unavailable for this review file.",
            ) from exc
        response = Response(content=body, media_type=content_type)
        response.headers["Content-Disposition"] = _private_content_disposition(
            filename,
            disposition="inline",
        )
    else:
        relative_path = _normalize_value(upload_record.get("relative_path"))
        absolute_path = _absolute_upload_path(relative_path)
        if not absolute_path.exists():
            raise HTTPException(status_code=404, detail="Upload file not found on disk.")
        response = FileResponse(
            path=absolute_path,
            media_type=content_type,
            filename=filename,
            content_disposition_type="inline",
        )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@router.get("/{upload_id}/preview")
def preview_upload(
    upload_id: str,
    viewer_project_id: str = Query(default=""),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Stream an authorized private upload without exposing its storage URL."""

    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")
    normalized_viewer_project_id = (
        _normalize_value(viewer_project_id)
        if isinstance(viewer_project_id, str)
        else ""
    )
    if normalized_viewer_project_id:
        upload_record, _context = _require_viewer_upload_access(
            upload_id,
            normalized_viewer_project_id,
            db,
            current_user,
            require_current=True,
        )
    else:
        upload_record, _context = _require_upload_access(
            upload_id,
            db,
            current_user,
            detail="Your active package does not include access to this upload.",
        )
    if _normalize_value(upload_record.get("deletion_status")).lower() in {"pending", "failed"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This file is unavailable while deletion is pending reconciliation.",
        )
    if _upload_scan_blocks_download(upload_record):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This file is unavailable until its security scan passes.",
        )
    if not _upload_has_durable_private_storage(upload_record):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="This file is unavailable until private storage migration completes.",
        )

    content_type = _normalize_value(upload_record.get("content_type")) or "application/octet-stream"
    filename = Path(
        _normalize_value(upload_record.get("original_filename")) or "vault-file"
    ).name.replace('"', "")
    if _normalize_value(upload_record.get("storage_provider")).lower() == "r2":
        storage_key = _normalize_value(upload_record.get("storage_key"))
        if not storage_key:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Private object storage key is missing for this upload.",
            )
        try:
            body = download_private_bytes(
                key=storage_key,
                max_bytes=_upload_read_limit(upload_record),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Private object storage is unavailable for this upload.",
            ) from exc
        response: Response = Response(content=body, media_type=content_type)
        response.headers["Content-Disposition"] = _private_content_disposition(
            filename,
            disposition="inline",
        )
    else:
        relative_path = _normalize_value(upload_record.get("relative_path"))
        if not relative_path:
            raise HTTPException(status_code=404, detail="Upload path missing.")
        absolute_path = _absolute_upload_path(relative_path)
        if not absolute_path.exists():
            raise HTTPException(status_code=404, detail="Upload file not found on disk.")
        response = FileResponse(
            path=absolute_path,
            media_type=content_type,
            filename=filename,
            content_disposition_type="inline",
        )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@router.get("/{upload_id}/download")
def download_upload(
    upload_id: str,
    admin_override: bool = Query(default=False),
    viewer_project_id: str = Query(default=""),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not connected.")

    normalized_viewer_project_id = (
        _normalize_value(viewer_project_id)
        if isinstance(viewer_project_id, str)
        else ""
    )
    if normalized_viewer_project_id:
        upload_record, _context = _require_viewer_upload_access(
            upload_id,
            normalized_viewer_project_id,
            db,
            current_user,
            require_current=True,
        )
    else:
        upload_record, _context = _require_upload_access(
            upload_id,
            db,
            current_user,
            detail="Your active package does not include upload access.",
        )
    deletion_status = _normalize_value(upload_record.get("deletion_status")).lower()
    if deletion_status in {"pending", "failed"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This file is unavailable while deletion is pending reconciliation.",
        )
    if not _upload_has_durable_private_storage(upload_record):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="This file is unavailable until private storage migration completes.",
        )
    if _upload_scan_blocks_download(upload_record):
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
                    {
                        "reason": "scan_not_clean",
                        "scan_status": _normalize_value(upload_record.get("scan_status")) or "unknown",
                    },
                )
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This file is unavailable until its security scan passes.",
            )

    if _normalize_value(upload_record.get("storage_provider")).lower() == "r2":
        storage_key = _normalize_value(upload_record.get("storage_key"))
        if not storage_key:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Private object storage key is missing for this upload.",
            )
        try:
            body = download_private_bytes(
                key=storage_key,
                max_bytes=_upload_read_limit(upload_record),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Private object storage is unavailable for this upload.",
            ) from exc
        content_type = (
            _normalize_value(upload_record.get("content_type"))
            or "application/octet-stream"
        )
        filename = Path(
            _normalize_value(upload_record.get("original_filename")) or "vault-file"
        ).name.replace('"', "")
        response = Response(content=body, media_type=content_type)
        response.headers["Content-Disposition"] = _private_content_disposition(
            filename,
            disposition="attachment",
        )
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

    existing_tombstone = None
    raw_upload_record = None
    if ObjectId.is_valid(upload_id):
        existing_tombstone = db["upload_deletion_tombstones"].find_one(
            {"_id": _deletion_tombstone_id(upload_id)}
        )
        raw_upload_record = db["uploaded_files"].find_one({"_id": ObjectId(upload_id)})
    same_retry_requester = bool(
        existing_tombstone
        and raw_upload_record
        and _normalize_value(existing_tombstone.get("requested_by_user_id"))
        == _current_user_id(current_user)
        and _normalize_value(raw_upload_record.get("deletion_requested_by_user_id"))
        == _current_user_id(current_user)
        and _normalize_value(raw_upload_record.get("deletion_status")).lower()
        in {"pending", "failed"}
    )

    try:
        if same_retry_requester:
            # Canonical Vault auth intentionally hides a tombstoned version.
            # A retry by the already-authorized deletion requester must still
            # be able to finish idempotent physical/metadata cleanup.
            upload_record = raw_upload_record
            context = resolve_workspace_context(
                current_user,
                project_id=_normalize_value(upload_record.get("project_id")),
                family_id=_normalize_value(upload_record.get("family_id")),
            )
        else:
            upload_record, context = _require_upload_management_access(
                upload_id,
                db,
                current_user,
                action="delete",
            )
    except HTTPException as exc:
        if exc.status_code != status.HTTP_404_NOT_FOUND or not ObjectId.is_valid(upload_id):
            raise
        existing_tombstone = existing_tombstone or db["upload_deletion_tombstones"].find_one(
            {"_id": _deletion_tombstone_id(upload_id)}
        )
        same_requester = bool(
            existing_tombstone
            and _normalize_value(existing_tombstone.get("requested_by_user_id"))
            == _current_user_id(current_user)
        )
        if not existing_tombstone or not (same_requester or _is_admin(current_user)):
            raise
        if (
            _normalize_value(existing_tombstone.get("category")).lower() == "private_media"
            and _normalize_value(existing_tombstone.get("vault_item_id"))
            and not bool(existing_tombstone.get("vault_version_tombstoned"))
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Vault deletion reconciliation is incomplete; the tombstone was retained.",
            )
        if _normalize_value(existing_tombstone.get("status")).lower() != "complete":
            _update_upload_deletion_tombstone(
                db=db,
                tombstone_id=_deletion_tombstone_id(upload_id),
                tombstone_status="complete",
                detail="idempotent_metadata_absent",
            )
        return {
            "status": "deleted",
            "upload_id": upload_id,
            "tombstone_id": _deletion_tombstone_id(upload_id),
            "idempotency_replayed": True,
        }

    if (
        _normalize_value(upload_record.get("category")).lower() == "private_media"
        and not same_retry_requester
    ):
        require_workspace_maintenance_write_access(context, feature_name="Vault")

    tombstone_id = _create_upload_deletion_tombstone(
        db=db,
        upload_record=upload_record,
        upload_id=upload_id,
        current_user=current_user,
    )

    relative_path = _normalize_value(upload_record.get("relative_path"))
    absolute_path = _absolute_upload_path(relative_path) if relative_path else None
    quarantine_path = _normalize_value(upload_record.get("quarantine_path"))
    absolute_quarantine_path = (
        _absolute_quarantine_path(quarantine_path) if quarantine_path else None
    )

    now = datetime.now(UTC).isoformat()
    db["uploaded_files"].update_one(
        {"_id": ObjectId(upload_id)},
        {
            "$set": {
                "deletion_status": "pending",
                "deletion_requested_at": now,
                "deletion_requested_by_user_id": _current_user_id(current_user),
                "updated_at": now,
            }
        },
    )

    try:
        _tombstone_linked_vault_upload_version(
            db=db,
            upload_record=upload_record,
            upload_id=upload_id,
            current_user=current_user,
            context=context,
            tombstone_id=tombstone_id,
        )
    except HTTPException as exc:
        detail_code = f"vault_version_tombstone_failed:{exc.status_code}"
        db["uploaded_files"].update_one(
            {"_id": ObjectId(upload_id)},
            {
                "$set": {
                    "deletion_status": "failed",
                    "deletion_detail": detail_code,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            },
        )
        _update_upload_deletion_tombstone(
            db=db,
            tombstone_id=tombstone_id,
            tombstone_status="failed",
            detail=detail_code,
        )
        raise

    if _normalize_value(upload_record.get("storage_provider")).lower() == "r2":
        storage_key = _normalize_value(upload_record.get("storage_key"))
        if not storage_key:
            db["uploaded_files"].update_one(
                {"_id": ObjectId(upload_id)},
                {
                    "$set": {
                        "deletion_status": "failed",
                        "deletion_detail": "private_storage_key_missing",
                        "updated_at": datetime.now(UTC).isoformat(),
                    }
                },
            )
            _update_upload_deletion_tombstone(
                db=db,
                tombstone_id=tombstone_id,
                tombstone_status="failed",
                detail="private_storage_key_missing",
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Private object storage key is missing; deletion was stopped safely.",
            )
        try:
            delete_private_object(key=storage_key)
        except Exception as exc:
            db["uploaded_files"].update_one(
                {"_id": ObjectId(upload_id)},
                {
                    "$set": {
                        "deletion_status": "failed",
                        "deletion_detail": (
                            f"private_storage_delete_failed:{type(exc).__name__}"
                        ),
                        "updated_at": datetime.now(UTC).isoformat(),
                    }
                },
            )
            _update_upload_deletion_tombstone(
                db=db,
                tombstone_id=tombstone_id,
                tombstone_status="failed",
                detail=f"private_storage_delete_failed:{type(exc).__name__}",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Private object storage deletion failed; the record was retained for retry.",
            )

    try:
        if absolute_path:
            absolute_path.unlink(missing_ok=True)

        if absolute_quarantine_path:
            absolute_quarantine_path.unlink(missing_ok=True)
    except OSError as exc:
        db["uploaded_files"].update_one(
            {"_id": ObjectId(upload_id)},
            {
                "$set": {
                    "deletion_status": "failed",
                    "deletion_detail": f"local_cleanup_failed:{type(exc).__name__}",
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            },
        )
        _update_upload_deletion_tombstone(
            db=db,
            tombstone_id=tombstone_id,
            tombstone_status="failed",
            detail=f"local_cleanup_failed:{type(exc).__name__}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload cleanup failed; the record was retained for retry.",
        )

    try:
        _clear_deleted_member_photo_references(
            db=db,
            upload_record=upload_record,
            upload_id=upload_id,
            current_user=current_user,
        )
    except Exception as exc:
        db["uploaded_files"].update_one(
            {"_id": ObjectId(upload_id)},
            {
                "$set": {
                    "deletion_status": "failed",
                    "deletion_detail": (
                        f"member_reference_cleanup_failed:{type(exc).__name__}"
                    ),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            },
        )
        _update_upload_deletion_tombstone(
            db=db,
            tombstone_id=tombstone_id,
            tombstone_status="failed",
            detail=f"member_reference_cleanup_failed:{type(exc).__name__}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Member portrait references could not be cleared; "
                "the upload record was retained for retry."
            ),
        )

    try:
        deletion_result = db["uploaded_files"].delete_one({"_id": ObjectId(upload_id)})
        if getattr(deletion_result, "deleted_count", 1) != 1:
            raise RuntimeError("upload_metadata_delete_missing")
    except Exception as exc:
        db["uploaded_files"].update_one(
            {"_id": ObjectId(upload_id)},
            {
                "$set": {
                    "deletion_status": "failed",
                    "deletion_detail": f"metadata_delete_failed:{type(exc).__name__}",
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            },
        )
        _update_upload_deletion_tombstone(
            db=db,
            tombstone_id=tombstone_id,
            tombstone_status="failed",
            detail=f"metadata_delete_failed:{type(exc).__name__}",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upload metadata deletion failed and was retained for reconciliation.",
        ) from exc
    _update_upload_deletion_tombstone(
        db=db,
        tombstone_id=tombstone_id,
        tombstone_status="complete",
    )

    actor = _actor_audit_identity(current_user)
    try:
        write_audit_log(
            actor_user_id=actor["user_id"],
            actor_email=actor["email"],
            actor_name=actor["name"],
            action="uploads.deleted",
            target_type="upload_tombstone",
            target_id=tombstone_id,
            before={"upload_id": upload_id, "category": upload_record.get("category")},
            after={"status": "complete"},
            context={"project_id": upload_record.get("project_id")},
        )
    except Exception:
        pass

    return {
        "status": "deleted",
        "upload_id": upload_id,
        "tombstone_id": tombstone_id,
    }
