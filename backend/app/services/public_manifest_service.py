from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, cast

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.errors import OperationFailure

from app.config import settings
from app.core.package_catalog import get_package
from app.database import get_database
from app.services.mint_policy_service import get_package_mint_policy
from app.services.poster_asset_service import build_poster_asset
from app.services.r2_storage_service import ZONE_METADATA, upload_json

SCHEMA_VERSION = "tol-nft-1.0"


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _to_object_id(value: str) -> ObjectId | None:
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def _collection() -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db["public_metadata_manifests"])


def _projects_collection() -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db["projects"])


def _certificates_collection() -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db["issued_certificates"])


def ensure_public_manifest_indexes() -> None:
    collection = _collection()
    existing = collection.index_information()

    definitions = [
        (
            [("project_id", 1), ("version_number", -1)],
            "project_id_1_version_number_-1",
            False,
            None,
        ),
        (
            [("public_token_id", 1)],
            "public_token_id_1",
            True,
            {"public_token_id": {"$type": "string"}},
        ),
        (
            [("mint_record_id", 1)],
            "mint_record_id_1",
            False,
            None,
        ),
    ]

    for keys, name, unique, partial in definitions:
        if name in existing:
            continue
        options: dict[str, Any] = {"name": name, "unique": unique}
        if partial is not None:
            options["partialFilterExpression"] = partial
        try:
            collection.create_index(keys, **options)
        except OperationFailure:
            continue


def _serialize_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _serialize_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _hash_sha256(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest().upper()}"


def _hash_salt() -> str:
    return _normalize(settings.hash_salt) or _normalize(settings.secret_key) or "change-me"


def _project_document(project_id: str) -> dict[str, Any]:
    oid = _to_object_id(project_id)
    if oid is None:
        raise ValueError("Project not found.")
    project = _projects_collection().find_one({"_id": oid})
    if project is None:
        raise ValueError("Project not found.")
    return project


def _latest_certificate(project: dict[str, Any]) -> dict[str, Any] | None:
    family_id = _normalize(project.get("family_id"))
    project_id = _normalize(project.get("_id") or project.get("id"))

    if family_id:
        certificate = _certificates_collection().find_one(
            {"family_id": family_id},
            sort=[("version", -1), ("issued_at", -1), ("created_at", -1)],
        )
        if certificate is not None:
            return certificate

    if project_id:
        certificate = _certificates_collection().find_one(
            {"project_id": project_id},
            sort=[("version", -1), ("issued_at", -1), ("created_at", -1)],
        )
        if certificate is not None:
            return certificate

    return None


def compute_project_ref_hash(project_id: str) -> str:
    return _hash_sha256(f"{_hash_salt()}:{_normalize(project_id)}")


def compute_household_ref_hash(household_id: str | None) -> str | None:
    normalized = _normalize(household_id)
    if not normalized:
        return None
    return _hash_sha256(f"{_hash_salt()}:{normalized}")


def compute_build_hash(project_id: str) -> str:
    project = _project_document(project_id)
    payload = {
        "project_id": _normalize(project.get("_id")),
        "package_code": _normalize(
            project.get("package_code")
            or project.get("package_slug")
            or project.get("package_type")
        ),
        "project_lane": _normalize(project.get("project_lane")),
        "family_id": _normalize(project.get("family_id")) or None,
        "household_id": _normalize(project.get("household_id")) or None,
        "organization_id": _normalize(project.get("organization_id")) or None,
        "status": _normalize(project.get("status")),
        "phase": _normalize(project.get("phase")),
        "updated_at": _serialize_value(project.get("updated_at") or project.get("created_at")),
    }
    return _hash_sha256(_canonical_json(payload))


def compute_certificate_hash(project_id: str) -> str | None:
    project = _project_document(project_id)
    certificate = _latest_certificate(project)
    if certificate is None:
        return None
    return _hash_sha256(_canonical_json(certificate))


def _build_public_token_id(project_id: str, version_number: int) -> str:
    suffix = (_normalize(project_id)[-6:] or "000000").upper()
    return f"TOL-{_now().year}-{suffix}-V{version_number:02d}"


def _default_name(public_token_id: str) -> str:
    return f"Tomb of Light Legacy Anchor #{public_token_id}"


def _default_description() -> str:
    return (
        "A public-safe onchain legacy anchor issued by Tomb of Light for an approved "
        "digital lineage build. Private family records remain off-chain in protected storage."
    )


def _token_external_url(public_token_id: str) -> str:
    return f"{settings.public_token_external_base_url.rstrip('/')}/{public_token_id}"


def _attributes_for_manifest(
    *,
    package_name: str,
    package_lane: str,
    token_type: str,
    version_number: int,
    poster_style: str,
) -> list[dict[str, Any]]:
    return [
        {"trait_type": "Package", "value": package_name},
        {"trait_type": "Lane", "value": package_lane},
        {"trait_type": "Token Type", "value": token_type},
        {"trait_type": "Version", "value": version_number},
        {"trait_type": "Privacy", "value": "public-safe"},
        {"trait_type": "Poster Style", "value": poster_style},
    ]


def _serialize_manifest(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _normalize(document.get("_id")),
        "project_id": _normalize(document.get("project_id")),
        "mint_record_id": _normalize(document.get("mint_record_id")),
        "version_number": int(document.get("version_number") or 1),
        "schema_version": _normalize(document.get("schema_version")) or SCHEMA_VERSION,
        "public_token_id": _normalize(document.get("public_token_id")),
        "metadata_uri": _normalize(document.get("metadata_uri")),
        "poster_image_uri_public": _normalize(document.get("poster_image_uri_public")),
        "payload": document.get("payload") or {},
        "build_hash": _normalize(document.get("build_hash")),
        "certificate_hash": _normalize(document.get("certificate_hash")) or None,
        "approval_status": _normalize(document.get("approval_status")) or "draft",
        "approved_by": _normalize(document.get("approved_by")) or None,
        "approved_at": document.get("approved_at"),
        "storage_provider": _normalize(document.get("storage_provider")) or None,
        "storage_bucket": _normalize(document.get("storage_bucket")) or None,
        "storage_key": _normalize(document.get("storage_key")) or None,
        "created_at": document.get("created_at") or _now(),
        "updated_at": document.get("updated_at") or _now(),
    }


def write_public_metadata(
    *,
    project_id: str,
    mint_record_id: str,
    version_number: int,
    public_token_id: str,
    metadata_uri: str,
    poster_image_uri_public: str,
    payload: dict[str, Any],
    build_hash: str,
    certificate_hash: str | None,
    approval_status: str = "draft",
    approved_by: str | None = None,
    approved_at: datetime | None = None,
) -> dict[str, Any]:
    collection = _collection()
    now = _now()
    publish = _normalize(approval_status).lower() == "approved"
    storage_write = upload_json(
        zone=ZONE_METADATA,
        key=f"tokens/{public_token_id}.json",
        payload=payload,
        publish=publish,
    )

    document: dict[str, Any] = {
        "project_id": project_id,
        "mint_record_id": mint_record_id,
        "version_number": version_number,
        "schema_version": SCHEMA_VERSION,
        "public_token_id": public_token_id,
        "metadata_uri": metadata_uri,
        "poster_image_uri_public": poster_image_uri_public,
        "payload": payload,
        "build_hash": build_hash,
        "certificate_hash": certificate_hash,
        "approval_status": approval_status,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "storage_provider": storage_write.get("storage_provider"),
        "storage_bucket": storage_write.get("bucket"),
        "storage_key": storage_write.get("key"),
        "updated_at": now,
    }

    existing = collection.find_one(
        {"mint_record_id": mint_record_id, "version_number": version_number}
    )

    if existing is not None:
        collection.update_one(
            {"_id": existing["_id"]},
            {"$set": document},
        )
        saved = collection.find_one({"_id": existing["_id"]}) or existing
    else:
        document["created_at"] = now
        result = collection.insert_one(document)
        saved = collection.find_one({"_id": result.inserted_id}) or document

    return _serialize_manifest(saved)


def build_public_manifest(
    project_id: str,
    version_number: int,
    *,
    mint_record_id: str = "",
    poster_style: str = "abstract_cover",
    public_title_opt_in: bool = False,
    public_title: str | None = None,
    public_title_kind: str = "none",
    approved_poster_opt_in: bool = False,
    approval_timestamp: datetime | None = None,
) -> dict[str, Any]:
    project = _project_document(project_id)
    package = get_package(
        _normalize(
            project.get("package_code")
            or project.get("package_slug")
            or project.get("package_type")
        )
    )
    if not package:
        raise ValueError("Project package could not be resolved.")

    package_code = _normalize(package.get("package_code"))
    package_name = _normalize(package.get("display_name")) or package_code
    package_lane = _normalize(package.get("package_lane")) or _normalize(
        project.get("project_lane")
    )
    policy = get_package_mint_policy(package_code)
    token_type = _normalize(policy.get("token_type")) or "portrait_anchor"
    public_token_id = _build_public_token_id(project_id, version_number)

    poster_asset = build_poster_asset(
        project_id=project_id,
        version_number=version_number,
        public_token_id=public_token_id,
        requested_style=poster_style,
        approved_poster_opt_in=approved_poster_opt_in,
        publish=approval_timestamp is not None,
    )
    resolved_poster_style = poster_asset["poster_style"]
    poster_image_uri_public = poster_asset["poster_image_uri_public"]

    metadata_uri = (
        f"{settings.metadata_base_url.rstrip('/')}/tokens/{public_token_id}.json"
    )
    project_ref_hash = compute_project_ref_hash(project_id)
    household_ref_hash = compute_household_ref_hash(project.get("household_id"))
    build_hash = compute_build_hash(project_id)
    certificate_hash = compute_certificate_hash(project_id)
    final_title = (
        _normalize(public_title)
        if public_title_opt_in and _normalize(public_title)
        else None
    )
    resolved_approval_timestamp = approval_timestamp or _now()

    payload = {
        "name": final_title or _default_name(public_token_id),
        "description": _default_description(),
        "image": poster_image_uri_public,
        "external_url": _token_external_url(public_token_id),
        "attributes": _attributes_for_manifest(
            package_name=package_name,
            package_lane=package_lane,
            token_type=token_type,
            version_number=version_number,
            poster_style=resolved_poster_style,
        ),
        "tol": {
            "schema_version": SCHEMA_VERSION,
            "token_type": token_type,
            "package_code": package_code,
            "package_lane": package_lane,
            "project_ref_hash": project_ref_hash,
            "household_ref_hash": household_ref_hash,
            "certificate_hash": certificate_hash,
            "build_hash": build_hash,
            "version_number": version_number,
            "approval_timestamp": resolved_approval_timestamp.isoformat(),
            "privacy_mode": "public-safe",
            "poster_style": resolved_poster_style,
            "public_title_opt_in": bool(public_title_opt_in),
            "public_title": final_title,
            "public_title_kind": _normalize(public_title_kind) or "none",
        },
    }

    return write_public_metadata(
        project_id=project_id,
        mint_record_id=mint_record_id,
        version_number=version_number,
        public_token_id=public_token_id,
        metadata_uri=metadata_uri,
        poster_image_uri_public=poster_image_uri_public,
        payload=payload,
        build_hash=build_hash,
        certificate_hash=certificate_hash,
        approval_status="draft" if approval_timestamp is None else "approved",
        approved_at=approval_timestamp,
    )


def get_public_manifest_for_mint_record(mint_record_id: str) -> dict[str, Any] | None:
    document = _collection().find_one(
        {"mint_record_id": mint_record_id},
        sort=[("version_number", -1), ("updated_at", -1)],
    )
    if document is None:
        return None
    return _serialize_manifest(document)


def get_public_manifest_by_token_id(public_token_id: str) -> dict[str, Any] | None:
    document = _collection().find_one({"public_token_id": public_token_id})
    if document is None:
        return None
    return _serialize_manifest(document)
