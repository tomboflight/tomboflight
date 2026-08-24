from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import settings


@dataclass
class UploadScanResult:
    status: str
    detail: str = ""


@dataclass
class UploadScannerConfiguration:
    configured: bool
    detail: str = ""


def _must_fail_closed() -> bool:
    environment = str(settings.environment or "development").strip().lower()
    production = environment not in {"development", "dev", "local", "test"}
    return production or bool(settings.upload_scan_fail_closed)


def _within_upload_root(path: Path) -> bool:
    try:
        upload_root = Path(settings.upload_root_path).resolve()
        path.resolve().relative_to(upload_root)
        return True
    except Exception:
        return False


def _resolve_hook() -> Callable[[str], object] | None:
    hook_path = str(settings.upload_scan_hook or "").strip()
    if not hook_path:
        return None
    module_name, separator, function_name = hook_path.partition(":")
    if not separator or not module_name.strip() or not function_name.strip():
        raise RuntimeError("UPLOAD_SCAN_HOOK must be formatted as 'module:function'.")
    module = importlib.import_module(module_name.strip())
    hook = getattr(module, function_name.strip())
    if not callable(hook):
        raise RuntimeError("UPLOAD_SCAN_HOOK target is not callable.")
    return hook


def get_upload_scanner_configuration() -> UploadScannerConfiguration:
    hook_path = str(settings.upload_scan_hook or "").strip()
    if not hook_path:
        return UploadScannerConfiguration(False, "scanner_not_configured")

    module_name, separator, function_name = hook_path.partition(":")
    if not separator or not module_name.strip() or not function_name.strip():
        return UploadScannerConfiguration(False, "scanner_hook_format_invalid")

    try:
        module = importlib.import_module(module_name.strip())
        hook = getattr(module, function_name.strip())
    except Exception:
        return UploadScannerConfiguration(False, "scanner_hook_unavailable")

    if not callable(hook):
        return UploadScannerConfiguration(False, "scanner_hook_not_callable")

    configuration_check = getattr(module, "configuration_ready", None)
    if configuration_check is None:
        return UploadScannerConfiguration(True, "scanner_hook_loaded")
    if not callable(configuration_check):
        return UploadScannerConfiguration(False, "scanner_configuration_check_invalid")

    try:
        result: Any = configuration_check()
    except Exception:
        return UploadScannerConfiguration(False, "scanner_provider_configuration_error")

    if isinstance(result, tuple):
        ready = bool(result[0]) if result else False
        detail = str(result[1] if len(result) > 1 else "")
    elif isinstance(result, dict):
        ready = bool(result.get("configured") or result.get("ready"))
        detail = str(result.get("detail") or "")
    else:
        ready = bool(result)
        detail = ""

    return UploadScannerConfiguration(
        ready,
        detail or ("scanner_provider_configured" if ready else "scanner_provider_not_configured"),
    )


def get_upload_scanner_health() -> dict[str, Any]:
    """Return minimized configuration and live-provider availability details."""

    configuration = get_upload_scanner_configuration()
    if not configuration.configured:
        return {
            "configured": False,
            "available": False,
            "detail": configuration.detail or "scanner_not_configured",
        }

    hook_path = str(settings.upload_scan_hook or "").strip()
    module_name, separator, _function_name = hook_path.partition(":")
    if not separator or not module_name.strip():
        return {
            "configured": False,
            "available": False,
            "detail": "scanner_hook_format_invalid",
        }

    try:
        module = importlib.import_module(module_name.strip())
        healthcheck = getattr(module, "healthcheck")
    except Exception:
        return {
            "configured": True,
            "available": False,
            "detail": "scanner_healthcheck_unavailable",
        }
    if not callable(healthcheck):
        return {
            "configured": True,
            "available": False,
            "detail": "scanner_healthcheck_not_callable",
        }

    try:
        result: Any = healthcheck()
    except Exception as exc:
        return {
            "configured": True,
            "available": False,
            "detail": f"scanner_healthcheck_error:{type(exc).__name__}",
        }

    if isinstance(result, dict):
        configured = bool(result.get("configured", True))
        available = bool(result.get("available") or result.get("ready"))
        detail = str(result.get("detail") or "")
    elif isinstance(result, tuple):
        available = bool(result[0]) if result else False
        configured = True
        detail = str(result[1] if len(result) > 1 else "")
    else:
        configured = True
        available = bool(result)
        detail = ""

    return {
        "configured": configured,
        "available": available,
        "detail": detail or ("scanner_ready" if available else "scanner_unavailable"),
    }


def _coerce_result(result: object) -> UploadScanResult:
    if isinstance(result, UploadScanResult):
        return result
    if isinstance(result, dict):
        return UploadScanResult(
            status=str(result.get("status") or "error"),
            detail=str(result.get("detail") or ""),
        )
    if isinstance(result, tuple) and len(result) >= 1:
        return UploadScanResult(
            status=str(result[0] or "error"),
            detail=str(result[1] if len(result) > 1 else ""),
        )
    if isinstance(result, bool):
        return UploadScanResult(status="clean" if result else "infected", detail="")
    return UploadScanResult(status="error", detail="invalid_scanner_result")


def scan_uploaded_file(path: str) -> UploadScanResult:
    file_path = str(Path(path).resolve())
    if not _within_upload_root(Path(file_path)):
        return UploadScanResult(status="error", detail="invalid_upload_path")

    try:
        hook = _resolve_hook()
    except Exception as exc:
        detail = f"scanner_configuration_error:{type(exc).__name__}"
        if _must_fail_closed():
            return UploadScanResult(status="error", detail=detail)
        return UploadScanResult(status="skipped", detail=detail)
    if hook is None:
        if bool(settings.upload_scan_command):
            detail = "scanner_command_execution_disabled_use_upload_scan_hook"
        else:
            detail = "scanner_not_configured"
        if _must_fail_closed():
            return UploadScanResult(status="error", detail=detail)
        return UploadScanResult(status="skipped", detail=detail)

    try:
        result = _coerce_result(hook(file_path))
    except Exception as exc:
        detail = f"scanner_error:{type(exc).__name__}"
        if _must_fail_closed():
            return UploadScanResult(status="error", detail=detail)
        return UploadScanResult(status="skipped", detail=detail)

    normalized_status = str(result.status or "").strip().lower()
    if normalized_status == "skipped" and _must_fail_closed():
        return UploadScanResult(
            status="error",
            detail=result.detail or "scanner_skipped_without_clean_verdict",
        )
    if normalized_status in {"clean", "infected", "error", "skipped"}:
        return UploadScanResult(status=normalized_status, detail=result.detail)
    return UploadScanResult(status="error", detail="invalid_scanner_status")
