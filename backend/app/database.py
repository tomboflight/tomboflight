from pymongo import MongoClient
from pymongo.database import Database
import certifi
import logging
import os
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlsplit

from app.config import settings

client: MongoClient | None = None
db: Database | None = None
logger = logging.getLogger(__name__)
_connection_lock = Lock()
_last_connection_attempt_monotonic = 0.0
_RECONNECT_COOLDOWN_SECONDS = 5.0
_connection_state_callback: Callable[[Database | None], None] | None = None


class DatabaseUnavailableError(RuntimeError):
    """Raised when a DB-required code path is invoked without an active DB connection."""


def set_mongo_connection_state_callback(
    callback: Callable[[Database | None], None] | None,
) -> None:
    """Keep framework-owned database references synchronized after reconnects."""

    global _connection_state_callback
    _connection_state_callback = callback
    _publish_connection_state()


def _publish_connection_state() -> None:
    callback = _connection_state_callback
    if callback is None:
        return
    try:
        callback(db)
    except Exception:
        logger.exception("MongoDB connection state callback failed.")


def _mongodb_tls_options(uri: str) -> dict[str, Any]:
    """Return safe TLS overrides without breaking ordinary local MongoDB.

    SRV URIs already enable TLS through PyMongo. An explicit ``tls``/``ssl``
    query option always wins. Standard remote URIs retain the previous secure
    default, while loopback and Unix-socket development URIs use the driver's
    normal non-TLS default.
    """

    parsed = urlsplit(uri)
    query_keys = {key.lower() for key in parse_qs(parsed.query, keep_blank_values=True)}
    if "tls" in query_keys or "ssl" in query_keys:
        return {}
    if parsed.scheme.lower() == "mongodb+srv":
        return {"tlsCAFile": certifi.where()}

    authority = parsed.netloc.rsplit("@", 1)[-1]
    host_tokens = [unquote(token.strip()) for token in authority.split(",") if token.strip()]
    local_hosts = True
    for token in host_tokens:
        if token.startswith("/"):
            continue
        if token.startswith("[") and "]" in token:
            hostname = token[1 : token.index("]")]
        else:
            hostname = token.rsplit(":", 1)[0] if token.count(":") == 1 else token
        if hostname.strip().lower() not in {"localhost", "127.0.0.1", "::1"}:
            local_hosts = False
            break

    if host_tokens and local_hosts:
        return {}
    return {"tls": True, "tlsCAFile": certifi.where()}


def _close_mongo_connection_unlocked() -> None:
    global client, db

    existing_client = client
    client = None
    db = None
    _publish_connection_state()
    if existing_client is not None:
        existing_client.close()


def _connect_to_mongo_unlocked(
    *,
    force: bool,
    publish_state: bool = True,
) -> Database | None:
    global client, db, _last_connection_attempt_monotonic

    if not settings.mongodb_uri:
        logger.warning("MongoDB URI is not set; starting without database connectivity.")
        _close_mongo_connection_unlocked()
        return None

    now = monotonic()
    if (
        not force
        and _last_connection_attempt_monotonic
        and now - _last_connection_attempt_monotonic < _RECONNECT_COOLDOWN_SECONDS
    ):
        return None
    _last_connection_attempt_monotonic = now

    candidate_client: MongoClient | None = None
    try:
        candidate_client = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
            **_mongodb_tls_options(settings.mongodb_uri),
        )
        candidate_db = candidate_client[settings.mongodb_db_name]
        candidate_client.admin.command("ping")
        previous_client = client
        client = candidate_client
        db = candidate_db
        if publish_state:
            _publish_connection_state()
        if previous_client is not None and previous_client is not candidate_client:
            previous_client.close()
        logger.info("Connected to MongoDB database", extra={"database": settings.mongodb_db_name})
        return db
    except Exception as exc:
        if candidate_client is not None:
            candidate_client.close()
        _close_mongo_connection_unlocked()
        # Avoid logging exception strings that may echo a credential-bearing URI.
        logger.error(
            "MongoDB connection failed; database connectivity is unavailable (%s).",
            type(exc).__name__,
        )
        return None


def connect_to_mongo() -> Database | None:
    """Establish a fresh MongoDB connection for application startup."""

    with _connection_lock:
        _close_mongo_connection_unlocked()
        return _connect_to_mongo_unlocked(force=True)


def ensure_mongo_connection() -> Database | None:
    """Live-ping MongoDB and reconnect after startup or transient outages."""

    current_db = db
    if current_db is not None:
        try:
            current_db.command("ping")
            return current_db
        except Exception:
            logger.warning("MongoDB readiness ping failed; attempting reconnection.")

    with _connection_lock:
        current_db = db
        if current_db is not None:
            try:
                current_db.command("ping")
                return current_db
            except Exception:
                _close_mongo_connection_unlocked()
        reconnected = _connect_to_mongo_unlocked(force=False, publish_state=False)
        if reconnected is None:
            return None
        try:
            # A process that started while MongoDB was unavailable still needs
            # the correctness-critical Vault/upload/message indexes before a
            # readiness probe can advertise the recovered connection.
            from app.services.db_bootstrap_service import ensure_runtime_data_indexes

            ensure_runtime_data_indexes()
        except Exception as exc:
            logger.error(
                "MongoDB reconnected but required runtime indexes are unavailable (%s).",
                type(exc).__name__,
            )
            _close_mongo_connection_unlocked()
            return None
        _publish_connection_state()
        return reconnected


def get_database() -> Database:
    # Reconnection is driven by the readiness probe so ordinary requests fail
    # fast with a structured 503 during an outage instead of each blocking on
    # a network connection attempt.
    if db is None:
        raise DatabaseUnavailableError("Database connection is currently unavailable.")
    return db


def get_service_state(
    *,
    include_operational_details: bool = False,
    reconnect_if_unavailable: bool = False,
) -> dict[str, Any]:
    # Import lazily so the services package can import get_database during
    # application startup without creating a database/services import cycle.
    from app.services.r2_storage_service import get_private_storage_health
    from app.services.upload_scan_service import (
        get_upload_scanner_configuration,
        get_upload_scanner_health,
    )

    active_db = (
        ensure_mongo_connection()
        if db is not None or reconnect_if_unavailable
        else None
    )
    database_connected = active_db is not None
    degraded_reasons = [] if database_connected else ["database_unavailable"]
    ready = database_connected
    service_mode = "ok" if ready else "degraded"
    release_sha = ""
    for key in (
        "RENDER_GIT_COMMIT",
        "RELEASE_SHA",
        "GIT_COMMIT",
        "COMMIT_SHA",
        "VERCEL_GIT_COMMIT_SHA",
    ):
        release_sha = str(os.environ.get(key) or "").strip()
        if release_sha:
            break

    postmark_token_file = str(settings.postmark_server_token_file or "").strip()
    postmark_token_configured = bool(str(settings.postmark_server_token or "").strip())
    if not postmark_token_configured and postmark_token_file:
        try:
            postmark_token_configured = bool(
                Path(postmark_token_file).is_file()
                and Path(postmark_token_file).stat().st_size > 0
            )
        except OSError:
            postmark_token_configured = False

    stripe_configured = bool(
        str(settings.stripe_secret_key or "").strip()
        and str(settings.stripe_publishable_key or "").strip()
        and str(settings.stripe_webhook_secret or "").strip()
    )
    postmark_configured = bool(
        postmark_token_configured
        and str(settings.postmark_from_email or "").strip()
    )
    scanner_configuration = get_upload_scanner_configuration()
    scanner_configured = scanner_configuration.configured
    if include_operational_details:
        scanner_health = get_upload_scanner_health()
        private_object_storage = get_private_storage_health(check_provider=True)
    else:
        scanner_health = {
            "configured": scanner_configured,
            "available": scanner_configured,
            "detail": scanner_configuration.detail,
        }
        private_object_storage = get_private_storage_health(check_provider=False)
    scanner_available = bool(scanner_health.get("available"))
    private_object_storage_configured = bool(
        private_object_storage.get("configured")
    )
    private_object_storage_available = bool(
        private_object_storage.get("available")
    )
    legacy_clean_local_uploads: int | None = None
    if include_operational_details and database_connected:
        try:
            legacy_clean_local_uploads = int(
                active_db["uploaded_files"].count_documents(
                    {
                        "scan_status": "clean",
                        "quarantined": {"$ne": True},
                        "storage_provider": {"$ne": "r2"},
                    }
                )
            )
        except Exception:
            legacy_clean_local_uploads = None
    mount_path_value = str(settings.render_disk_mount_path or "").strip()
    mount_path = Path(mount_path_value) if mount_path_value else None
    persistent_private_storage = bool(
        mount_path
        and mount_path.is_dir()
        and os.access(mount_path, os.R_OK | os.W_OK)
    )
    secret_key = str(settings.secret_key or "")
    signing_key_configured = bool(
        len(secret_key.encode("utf-8")) >= 32
        and secret_key.strip().lower()
        not in {"", "change-me", "changeme", "replace-me", "secret"}
    )
    kill_switch_raw = str(
        os.environ.get("CONTINUITY_EXECUTION_KILL_SWITCH") or ""
    ).strip().lower()
    continuity_execution_enabled = kill_switch_raw not in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }

    operational_degraded_reasons: list[str] = list(degraded_reasons)
    if settings.is_production_environment:
        if not signing_key_configured:
            operational_degraded_reasons.append("production_signing_key_invalid")
        if not stripe_configured:
            operational_degraded_reasons.append("stripe_configuration_incomplete")
        if not postmark_configured:
            operational_degraded_reasons.append("postmark_configuration_incomplete")
        if not scanner_configured or not scanner_available:
            operational_degraded_reasons.append("upload_scanner_unavailable_quarantine_only")
        if not persistent_private_storage:
            operational_degraded_reasons.append("private_upload_storage_not_persistent")
        if not private_object_storage_configured:
            operational_degraded_reasons.append("private_object_storage_not_configured")
        elif not private_object_storage_available:
            operational_degraded_reasons.append("private_object_storage_unavailable")
        if include_operational_details:
            if legacy_clean_local_uploads is None:
                operational_degraded_reasons.append(
                    "legacy_private_upload_inventory_unavailable"
                )
            elif legacy_clean_local_uploads:
                operational_degraded_reasons.append(
                    "legacy_private_uploads_pending_r2_migration"
                )
        if not release_sha:
            operational_degraded_reasons.append("deployment_revision_unavailable")
        if not continuity_execution_enabled:
            operational_degraded_reasons.append("continuity_execution_disabled")
        if not settings.nft_mint_enabled:
            operational_degraded_reasons.append("nft_mint_runtime_disabled")
        elif not settings.nft_mint_worker_enabled:
            operational_degraded_reasons.append("nft_controlled_worker_disabled")
        if settings.nft_auto_mint_on_review_enabled:
            operational_degraded_reasons.append("unsafe_nft_auto_mint_on_review_enabled")
        if not settings.nft_legacy_payment_links_disabled:
            operational_degraded_reasons.append("legacy_nft_payment_links_not_confirmed_disabled")

    operational_ready = ready and not operational_degraded_reasons
    service_state: dict[str, Any] = {
        "database_connected": database_connected,
        "service_mode": service_mode,
        "ready": ready,
        "degraded_reasons": degraded_reasons,
        "operational_ready": operational_ready,
    }
    if not include_operational_details:
        # Public liveness and readiness surfaces intentionally omit exact
        # security-control configuration. Detailed operational diagnostics are
        # available only through the authenticated CEO endpoint.
        return service_state

    service_state.update({
        "operational_degraded_reasons": operational_degraded_reasons,
        "release": {
            "version": settings.app_version,
            "commit": release_sha or None,
        },
        "components": {
            "database": {"ready": database_connected},
            "production_signing_key": {"configured": signing_key_configured},
            "stripe_webhooks": {"configured": stripe_configured},
            "transactional_email": {"configured": postmark_configured},
            "upload_scanner": {
                "configured": scanner_configured,
                "available": scanner_available,
                "fail_closed": bool(settings.upload_scan_fail_closed),
                "mode": "active" if scanner_available else "quarantine_only",
                "configuration_detail": scanner_configuration.detail,
                "health_detail": str(scanner_health.get("detail") or ""),
                "legacy_command_ignored": bool(
                    str(settings.upload_scan_command or "").strip()
                ),
            },
            "private_upload_storage": {
                "persistent": persistent_private_storage,
                "mode": "staging_disk" if persistent_private_storage else "local_runtime",
            },
            "private_object_storage": {
                "configured": private_object_storage_configured,
                "available": private_object_storage_available,
                "mode": "private_r2" if private_object_storage_available else "unavailable",
                "health_detail": str(private_object_storage.get("detail") or ""),
                "legacy_clean_local_uploads": legacy_clean_local_uploads,
            },
            "continuity_kernel": {
                "execution_enabled": continuity_execution_enabled,
            },
            "nft_runtime": {
                "enabled": bool(settings.nft_mint_enabled),
                "controlled_worker_enabled": bool(settings.nft_mint_worker_enabled),
                "checkout_auto_mint_disabled": not bool(
                    settings.nft_auto_mint_on_review_enabled
                ),
                "legacy_payment_links_confirmed_disabled": bool(
                    settings.nft_legacy_payment_links_disabled
                ),
                "purchase_accepting": bool(
                    settings.nft_mint_enabled
                    and settings.nft_mint_worker_enabled
                    and not settings.nft_auto_mint_on_review_enabled
                    and (
                        not settings.is_production_environment
                        or settings.nft_legacy_payment_links_disabled
                    )
                ),
            },
        },
    })
    return service_state


def close_mongo_connection() -> None:
    with _connection_lock:
        had_client = client is not None
        _close_mongo_connection_unlocked()
    if had_client:
        logger.info("MongoDB connection closed.")
