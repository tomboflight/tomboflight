from __future__ import annotations

import subprocess
import shlex
from dataclasses import dataclass
from pathlib import Path

from app.config import settings


@dataclass
class UploadScanResult:
    status: str
    detail: str = ""


def scan_uploaded_file(path: str) -> UploadScanResult:
    command = str(settings.upload_scan_command or "").strip()
    if not command:
        if bool(settings.upload_scan_fail_closed):
            return UploadScanResult(status="error", detail="scanner_not_configured")
        return UploadScanResult(status="skipped", detail="scanner_not_configured")

    file_path = str(Path(path).resolve())
    command_template = command.replace("{path}", "{file_path}")
    command_parts = shlex.split(command_template.format(file_path=file_path))
    try:
        result = subprocess.run(
            command_parts,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as exc:
        if bool(settings.upload_scan_fail_closed):
            return UploadScanResult(status="error", detail=f"scanner_error:{exc}")
        return UploadScanResult(status="skipped", detail=f"scanner_error:{exc}")

    if result.returncode == 0:
        return UploadScanResult(status="clean", detail="clean")

    if bool(settings.upload_scan_fail_closed):
        return UploadScanResult(
            status="infected",
            detail=(result.stderr or result.stdout or "scanner_reported_failure").strip(),
        )

    return UploadScanResult(
        status="skipped",
        detail=(result.stderr or result.stdout or "scanner_reported_failure").strip(),
    )
