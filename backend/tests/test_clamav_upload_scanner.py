from __future__ import annotations

from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from app.services import clamav_upload_scanner
from app.services import upload_scan_service


class FakeClamavSocket:
    def __init__(self, response: bytes, peer: str = "10.0.0.8") -> None:
        self.response = response
        self.peer = peer
        self.sent = bytearray()
        self.closed = False
        self.timeout = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def settimeout(self, timeout: float) -> None:
        self.timeout = timeout

    def getpeername(self):
        return self.peer, 3310

    def sendall(self, payload: bytes) -> None:
        self.sent.extend(payload)

    def recv(self, _size: int) -> bytes:
        response, self.response = self.response, b""
        return response

    def close(self) -> None:
        self.closed = True


class ClamavUploadScannerTests(unittest.TestCase):
    def _scanner_settings(self):
        return (
            patch.object(clamav_upload_scanner.settings, "upload_clamav_host", "clamav.internal"),
            patch.object(clamav_upload_scanner.settings, "upload_clamav_port", 3310),
            patch.object(clamav_upload_scanner.settings, "upload_clamav_timeout_seconds", 5.0),
            patch.object(
                clamav_upload_scanner.settings,
                "upload_clamav_require_private_network",
                True,
            ),
        )

    def test_configuration_requires_clamav_host(self):
        with patch.object(clamav_upload_scanner.settings, "upload_clamav_host", ""):
            configured, detail = clamav_upload_scanner.configuration_ready()
        self.assertFalse(configured)
        self.assertEqual(detail, "clamav_host_missing")

    def test_healthcheck_refuses_public_network_peer(self):
        connection = FakeClamavSocket(b"PONG\0", peer="8.8.8.8")
        first, second, third, fourth = self._scanner_settings()
        with (
            first,
            second,
            third,
            fourth,
            patch.object(
                clamav_upload_scanner.socket,
                "create_connection",
                return_value=connection,
            ),
        ):
            result = clamav_upload_scanner.healthcheck()
        self.assertTrue(result["configured"])
        self.assertFalse(result["available"])
        self.assertEqual(result["detail"], "clamav_unavailable:RuntimeError")
        self.assertTrue(connection.closed)

    def test_scan_streams_file_and_accepts_clean_verdict(self):
        connection = FakeClamavSocket(b"stream: OK\0")
        first, second, third, fourth = self._scanner_settings()
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "portrait.jpg"
            file_path.write_bytes(b"portrait-bytes")
            with (
                first,
                second,
                third,
                fourth,
                patch.object(
                    clamav_upload_scanner.socket,
                    "create_connection",
                    return_value=connection,
                ),
            ):
                result = clamav_upload_scanner.scan(str(file_path))

        self.assertEqual(result, {"status": "clean", "detail": "clamav_clean"})
        self.assertTrue(connection.sent.startswith(b"zINSTREAM\0"))
        self.assertIn(struct.pack("!I", len(b"portrait-bytes")) + b"portrait-bytes", connection.sent)
        self.assertTrue(connection.sent.endswith(struct.pack("!I", 0)))

    def test_scan_returns_infected_without_exposing_file_path(self):
        connection = FakeClamavSocket(b"stream: Win.Test.EICAR_HDB-1 FOUND\0")
        first, second, third, fourth = self._scanner_settings()
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "eicar.txt"
            file_path.write_bytes(b"test")
            with (
                first,
                second,
                third,
                fourth,
                patch.object(
                    clamav_upload_scanner.socket,
                    "create_connection",
                    return_value=connection,
                ),
            ):
                result = clamav_upload_scanner.scan(str(file_path))

        self.assertEqual(result["status"], "infected")
        self.assertIn("Win.Test.EICAR_HDB-1", result["detail"])
        self.assertNotIn(str(file_path), result["detail"])

    def test_readiness_validates_import_and_provider_configuration(self):
        with patch.object(upload_scan_service.settings, "upload_scan_hook", "missing.module:scan"):
            missing = upload_scan_service.get_upload_scanner_configuration()
        self.assertFalse(missing.configured)
        self.assertEqual(missing.detail, "scanner_hook_unavailable")

        with (
            patch.object(
                upload_scan_service.settings,
                "upload_scan_hook",
                "app.services.clamav_upload_scanner:scan",
            ),
            patch.object(upload_scan_service.settings, "upload_clamav_host", ""),
        ):
            unconfigured = upload_scan_service.get_upload_scanner_configuration()
        self.assertFalse(unconfigured.configured)
        self.assertEqual(unconfigured.detail, "clamav_host_missing")

    def test_invalid_hook_fails_closed_instead_of_raising(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "pending.pdf"
            file_path.write_bytes(b"pending")
            with (
                patch.object(upload_scan_service.settings, "environment", "production"),
                patch.object(upload_scan_service.settings, "upload_scan_hook", "missing.module:scan"),
                patch.object(upload_scan_service.settings, "upload_storage_dir", tmpdir),
                patch.object(upload_scan_service.settings, "render_disk_mount_path", ""),
            ):
                result = upload_scan_service.scan_uploaded_file(str(file_path))
        self.assertEqual(result.status, "error")
        self.assertEqual(result.detail, "scanner_configuration_error:ModuleNotFoundError")

    def test_quarantine_root_follows_persistent_disk(self):
        with tempfile.TemporaryDirectory() as mount_path:
            with patch.object(
                upload_scan_service.settings,
                "render_disk_mount_path",
                mount_path,
            ):
                resolved = upload_scan_service.settings.upload_quarantine_root_path
        self.assertEqual(resolved, str(Path(mount_path) / "quarantine"))


if __name__ == "__main__":
    unittest.main()
