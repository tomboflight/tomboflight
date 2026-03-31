from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings

ZONE_METADATA = "metadata"
ZONE_POSTER = "poster"
ZONE_PRIVATE = "private"


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _public_storage_root() -> Path:
    root = Path(settings.public_storage_root_path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _metadata_bucket() -> str:
    return (
        _normalize(settings.r2_metadata_bucket)
        or _normalize(settings.r2_bucket)
    )


def _poster_bucket() -> str:
    return (
        _normalize(settings.r2_poster_bucket)
        or _normalize(settings.r2_bucket)
    )


def _private_bucket() -> str:
    return (
        _normalize(settings.r2_private_bucket)
        or _normalize(settings.r2_bucket)
    )


def _has_any_r2_config() -> bool:
    return any(
        (
            _normalize(settings.r2_account_id),
            _normalize(settings.r2_access_key_id),
            _normalize(settings.r2_secret_access_key),
            _normalize(settings.r2_endpoint_url),
            _normalize(settings.r2_bucket),
            _normalize(settings.r2_metadata_bucket),
            _normalize(settings.r2_poster_bucket),
            _normalize(settings.r2_private_bucket),
        )
    )


def r2_is_configured() -> bool:
    return all(
        (
            _normalize(settings.r2_access_key_id),
            _normalize(settings.r2_secret_access_key),
            _normalize(settings.r2_resolved_endpoint_url),
            _metadata_bucket() or _poster_bucket() or _private_bucket(),
        )
    )


def _allow_local_fallback() -> bool:
    environment = _normalize(settings.environment).lower()
    if _has_any_r2_config():
        return False
    return environment in {"", "development", "dev", "local", "test", "testing"}


def _bucket_for_zone(zone: str) -> str:
    normalized = _normalize(zone).lower()
    if normalized == ZONE_METADATA:
        return _metadata_bucket()
    if normalized == ZONE_POSTER:
        return _poster_bucket()
    if normalized == ZONE_PRIVATE:
        return _private_bucket()
    return _normalize(settings.r2_bucket)


def _lazy_s3_client():
    try:
        import boto3 # type: ignore
        from botocore.config import Config # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "boto3 is required for R2 storage writes. Install backend requirements "
            "before enabling R2-backed metadata or poster storage."
        ) from exc

    endpoint_url = _normalize(settings.r2_resolved_endpoint_url)
    if not endpoint_url:
        raise RuntimeError("R2 endpoint is not configured.")

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=_normalize(settings.r2_region) or "auto",
        aws_access_key_id=_normalize(settings.r2_access_key_id),
        aws_secret_access_key=_normalize(settings.r2_secret_access_key),
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if settings.r2_force_path_style else "virtual"},
        ),
    )


def _local_fallback_write(
    *,
    zone: str,
    key: str,
    body: bytes,
) -> dict[str, Any]:
    destination = _public_storage_root() / _normalize(zone).lower() / key
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(body)

    return {
        "storage_provider": "local_disk",
        "bucket": None,
        "key": key,
        "size_bytes": len(body),
        "local_path": str(destination),
    }


def upload_bytes(
    *,
    zone: str,
    key: str,
    body: bytes,
    content_type: str,
    cache_control: str = "public, max-age=300",
    publish: bool = True,
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    normalized_key = key.lstrip("/")
    del publish
    storage_key = normalized_key
    bucket = _bucket_for_zone(zone)

    if not r2_is_configured() or not bucket:
        if _allow_local_fallback():
            return _local_fallback_write(zone=zone, key=storage_key, body=body)
        raise RuntimeError(
            "R2 storage is not fully configured for this environment. "
            "Refusing to fall back to local public storage."
        )

    client = _lazy_s3_client()
    client.put_object(
        Bucket=bucket,
        Key=storage_key,
        Body=body,
        ContentType=content_type,
        CacheControl=cache_control,
        Metadata=metadata or {},
    )

    return {
        "storage_provider": "r2",
        "bucket": bucket,
        "key": storage_key,
        "size_bytes": len(body),
        "content_type": content_type,
    }


def upload_json(
    *,
    zone: str,
    key: str,
    payload: dict[str, Any],
    publish: bool = True,
) -> dict[str, Any]:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2).encode("utf-8")
    return upload_bytes(
        zone=zone,
        key=key,
        body=encoded,
        content_type="application/json",
        cache_control="public, max-age=300",
        publish=publish,
    )


def upload_text(
    *,
    zone: str,
    key: str,
    text: str,
    content_type: str,
    publish: bool = True,
) -> dict[str, Any]:
    return upload_bytes(
        zone=zone,
        key=key,
        body=text.encode("utf-8"),
        content_type=content_type,
        cache_control="public, max-age=300",
        publish=publish,
    )
