from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.database import get_database


CINEMATIC_MANIFEST_SCHEMA_VERSION = "tol-private-cinematic-manifest-1.0"


def _now() -> datetime:
    return datetime.now(UTC)


def _value(value: Any) -> str:
    return str(value or "").strip()


def _serialize(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    return value


def _manifest_content(manifest: dict[str, Any]) -> dict[str, Any]:
    content = deepcopy(manifest)
    content.pop("manifest_version", None)
    return _serialize(content)


def canonical_manifest_hash(manifest: dict[str, Any]) -> str:
    canonical = json.dumps(
        _manifest_content(manifest),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def ensure_cinematic_manifest_indexes() -> None:
    """Create the fail-closed indexes used by immutable private manifests."""

    db = get_database()
    if db is None:
        return

    versions = db["cinematic_manifest_versions"]
    active = db["cinematic_manifest_active"]
    versions.create_index(
        [("version_key", 1)],
        name="cinematic_manifest_version_key_unique",
        unique=True,
    )
    versions.create_index(
        [("project_id", 1), ("created_at", -1)],
        name="cinematic_manifest_project_created",
    )
    active.create_index(
        [("project_id", 1)],
        name="cinematic_manifest_active_project_unique",
        unique=True,
    )


def _validate_compiled_manifest(manifest: dict[str, Any]) -> None:
    compiler = manifest.get("cinema_compiler") or {}
    validation = compiler.get("validation") or {}
    if not bool(validation.get("complete")):
        raise RuntimeError(
            "Cinematic manifest publication failed closed because the family tour is incomplete."
        )
    if not bool(validation.get("tour_bounded")):
        raise RuntimeError(
            "Cinematic manifest publication failed closed because the family tour is not bounded."
        )
    state_ids = {
        _value(state.get("id"))
        for state in manifest.get("states") or []
        if _value(state.get("id")) and _value(state.get("member_id"))
    }
    tour_ids = {
        _value(state_id)
        for state_id in manifest.get("auto_advance_state_ids") or []
        if _value(state_id)
    }
    if state_ids != tour_ids:
        raise RuntimeError(
            "Cinematic manifest publication failed closed because approved portraits are missing from the tour."
        )


def publish_private_cinematic_manifest(
    manifest: dict[str, Any],
    *,
    project_id: str,
    family_id: str = "",
) -> dict[str, Any]:
    """Persist an immutable manifest, then atomically move its active pointer.

    The version insert always happens before the one-document pointer update. If
    the pointer update fails, MongoDB leaves the prior active pointer untouched.
    The caller receives the new manifest only after both writes succeed.
    """

    normalized_project_id = _value(project_id)
    if not normalized_project_id:
        raise RuntimeError("Project id is required to publish a cinematic manifest.")
    _validate_compiled_manifest(manifest)

    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")

    content_hash = canonical_manifest_hash(manifest)
    version_key = f"{normalized_project_id}:{content_hash}"
    versions = db["cinematic_manifest_versions"]
    active = db["cinematic_manifest_active"]
    now = _now()
    compiler = manifest.get("cinema_compiler") or {}
    snapshot = _manifest_content(manifest)
    version_document = {
        "version_key": version_key,
        "schema_version": CINEMATIC_MANIFEST_SCHEMA_VERSION,
        "compiler_version": _value(compiler.get("version")),
        "project_id": normalized_project_id,
        "family_id": _value(family_id) or None,
        "content_hash": content_hash,
        "publication_scope": "private_authenticated_viewer",
        "manifest_snapshot": snapshot,
        "created_at": now,
    }

    existing = versions.find_one({"version_key": version_key})
    if existing is None:
        try:
            result = versions.insert_one(version_document)
            version_id = _value(getattr(result, "inserted_id", "")) or version_key
        except DuplicateKeyError:
            existing = versions.find_one({"version_key": version_key})
            if existing is None:
                raise
            version_id = _value(existing.get("_id")) or version_key
    else:
        version_id = _value(existing.get("_id")) or version_key

    active_document = active.find_one({"project_id": normalized_project_id})
    if _value((active_document or {}).get("active_version_key")) != version_key:
        active.update_one(
            {"project_id": normalized_project_id},
            {
                "$set": {
                    "project_id": normalized_project_id,
                    "family_id": _value(family_id) or None,
                    "active_version_id": version_id,
                    "active_version_key": version_key,
                    "content_hash": content_hash,
                    "compiler_version": _value(compiler.get("version")),
                    "schema_version": CINEMATIC_MANIFEST_SCHEMA_VERSION,
                    "activated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    published = deepcopy(manifest)
    published["manifest_version"] = {
        "schema_version": CINEMATIC_MANIFEST_SCHEMA_VERSION,
        "compiler_version": _value(compiler.get("version")),
        "version_id": version_id,
        "content_hash": content_hash,
        "persisted": True,
    }
    return published


__all__ = [
    "CINEMATIC_MANIFEST_SCHEMA_VERSION",
    "canonical_manifest_hash",
    "ensure_cinematic_manifest_indexes",
    "publish_private_cinematic_manifest",
]
