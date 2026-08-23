from pymongo import MongoClient
from pymongo.database import Database
import certifi
import logging
import os
from pathlib import Path
from typing import Any

from app.config import settings

client: MongoClient | None = None
db: Database | None = None
logger = logging.getLogger(__name__)


class DatabaseUnavailableError(RuntimeError):
    """Raised when a DB-required code path is invoked without an active DB connection."""


def connect_to_mongo() -> Database | None:
    global client, db

    if not settings.mongodb_uri:
        logger.warning("MongoDB URI is not set; starting without database connectivity.")
        return None

    try:
        client = MongoClient(
            settings.mongodb_uri,
            tls=True,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            socketTimeoutMS=10000,
        )
        db = client[settings.mongodb_db_name]
        client.admin.command("ping")
        logger.info("Connected to MongoDB database", extra={"database": settings.mongodb_db_name})
        return db
    except Exception as exc:
        client = None
        db = None
        logger.error("MongoDB connection failed; starting without database connectivity: %s", exc)
        return None


def get_database() -> Database:
    if db is None:
        raise DatabaseUnavailableError("Database connection is currently unavailable.")
    return db


def get_service_state(*, include_operational_details: bool = False) -> dict[str, Any]:
    database_connected = db is not None
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
    scanner_hook = str(settings.upload_scan_hook or "").strip()
    scanner_configured = bool(
        scanner_hook
        and ":" in scanner_hook
        and scanner_hook.partition(":")[0].strip()
        and scanner_hook.partition(":")[2].strip()
    )
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
        if not scanner_configured:
            operational_degraded_reasons.append("upload_scanner_unavailable_quarantine_only")
        if not persistent_private_storage:
            operational_degraded_reasons.append("private_upload_storage_not_persistent")
        if not release_sha:
            operational_degraded_reasons.append("deployment_revision_unavailable")
        if not continuity_execution_enabled:
            operational_degraded_reasons.append("continuity_execution_disabled")

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
                "fail_closed": bool(settings.upload_scan_fail_closed),
                "mode": "active" if scanner_configured else "quarantine_only",
                "legacy_command_ignored": bool(
                    str(settings.upload_scan_command or "").strip()
                ),
            },
            "private_upload_storage": {
                "persistent": persistent_private_storage,
                "mode": "persistent_disk" if persistent_private_storage else "local_runtime",
            },
            "continuity_kernel": {
                "execution_enabled": continuity_execution_enabled,
            },
            "nft_runtime": {
                "enabled": bool(settings.nft_mint_enabled),
            },
        },
    })
    return service_state


def close_mongo_connection() -> None:
    global client, db

    if client is not None:
        client.close()
        logger.info("MongoDB connection closed.")

    client = None
    db = None
