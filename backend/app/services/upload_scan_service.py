from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.config import settings


@dataclass
class UploadScanResult:
    status: str
    detail: str = ""


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

    hook = _resolve_hook()
    if hook is None:
        if bool(settings.upload_scan_command):
            detail = "scanner_command_execution_disabled_use_upload_scan_hook"
        else:
            detail = "scanner_not_configured"
        if bool(settings.upload_scan_fail_closed):
            return UploadScanResult(status="error", detail=detail)
        return UploadScanResult(status="skipped", detail=detail)

    try:
        result = _coerce_result(hook(file_path))
    except Exception as exc:
        if bool(settings.upload_scan_fail_closed):
            return UploadScanResult(status="error", detail=f"scanner_error:{exc}")
        return UploadScanResult(status="skipped", detail=f"scanner_error:{exc}")

    normalized_status = str(result.status or "").strip().lower()
    if normalized_status in {"clean", "infected", "error", "skipped"}:
        return UploadScanResult(status=normalized_status, detail=result.detail)
    return UploadScanResult(status="error", detail="invalid_scanner_status")
