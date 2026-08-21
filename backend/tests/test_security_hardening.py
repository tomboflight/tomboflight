import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException

from app.core import security as security_core
from app.core.security import create_csrf_token, verify_csrf_token
from app.database import DatabaseUnavailableError
from app.routes import uploads as upload_routes
from app.services import auth_service, link_key_service, rate_limit_service, upload_scan_service


class FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])

    def find_one(self, query=None, sort=None):
        query = query or {}
        candidates = [item for item in self.documents if self._matches(item, query)]
        if sort and candidates:
            key, direction = sort[0]
            candidates.sort(key=lambda item: str(item.get(key) or ""), reverse=direction < 0)
        return candidates[0] if candidates else None

    def find(self, query=None):
        query = query or {}
        return [item for item in self.documents if self._matches(item, query)]

    def insert_one(self, document):
        stored = dict(document)
        stored["_id"] = stored.get("_id") or ObjectId()
        self.documents.append(stored)
        return FakeInsertResult(stored["_id"])

    def update_one(self, query, update):
        item = self.find_one(query)
        if not item:
            return
        item.update(update.get("$set", {}))

    def update_many(self, query, update):
        for item in self.find(query):
            item.update(update.get("$set", {}))

    def _matches(self, item, query):
        for key, expected in query.items():
            value = item.get(key)
            if isinstance(expected, dict):
                if "$in" in expected:
                    if value not in expected["$in"]:
                        return False
                elif "$ne" in expected:
                    if value == expected["$ne"]:
                        return False
                elif "$nin" in expected:
                    if value in expected["$nin"]:
                        return False
                else:
                    return False
            elif value != expected:
                return False
        return True


class FakeDatabase:
    def __init__(self, collections=None):
        self.collections = {
            name: FakeCollection(documents) for name, documents in (collections or {}).items()
        }

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]

    def __getattr__(self, name):
        return self[name]


class CsrfTokenTests(unittest.TestCase):
    def test_csrf_token_roundtrip(self):
        token = create_csrf_token("user-123", ttl_minutes=5)
        self.assertTrue(verify_csrf_token(token, user_id="user-123"))
        self.assertFalse(verify_csrf_token(token, user_id="other-user"))


class SigningKeyTests(unittest.TestCase):
    def test_production_signing_key_must_be_at_least_32_bytes(self):
        with (
            patch.object(security_core.settings, "environment", "production"),
            patch.object(security_core.settings, "secret_key", "too-short"),
        ):
            with self.assertRaisesRegex(RuntimeError, "at least 32 bytes"):
                security_core._resolve_secret_key()


class RateLimitAndLockoutTests(unittest.TestCase):
    def test_lockout_after_repeated_failures(self):
        key = "ip:test@example.com"
        with patch.object(rate_limit_service, "_LOCKOUTS", {}), patch.object(
            rate_limit_service, "_REQUEST_BUCKETS", {}
        ):
            locked = rate_limit_service.record_failure(
                scope="login",
                key=key,
                lockout_threshold=2,
                lockout_seconds=300,
            )
            self.assertFalse(locked)
            locked = rate_limit_service.record_failure(
                scope="login",
                key=key,
                lockout_threshold=2,
                lockout_seconds=300,
            )
            self.assertTrue(locked)
            with self.assertRaises(HTTPException):
                rate_limit_service.enforce_lockout(scope="login", key=key)


class AuthMfaTests(unittest.TestCase):
    def test_internal_admin_without_mfa_authenticates_normally(self):
        user_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": "admin@example.com",
                        "status": "active",
                        "password_hash": auth_service.hash_password("StrongPass!123"),
                        "role": "admin",
                        "access_tier": "super_admin",
                        "mfa_enabled": False,
                        "session_token_version": 0,
                    }
                ]
            }
        )
        with patch.object(auth_service, "get_database", return_value=db):
            result = auth_service.authenticate_user("admin@example.com", "StrongPass!123")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["status"], "authenticated")
        self.assertTrue(result.get("access_token"))
        self.assertFalse(result.get("mfa_challenge_token"))
        stored = db.users.find_one({"_id": user_id})
        self.assertIsNone(stored.get("mfa_pending_secret_encrypted"))
        self.assertIsNone(stored.get("mfa_pending_started_at"))

    def test_mfa_enabled_user_requires_verification(self):
        user_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": "admin@example.com",
                        "status": "active",
                        "password_hash": auth_service.hash_password("StrongPass!123"),
                        "role": "admin",
                        "access_tier": "super_admin",
                        "mfa_enabled": True,
                        "session_token_version": 0,
                    }
                ]
            }
        )
        with patch.object(auth_service, "get_database", return_value=db):
            result = auth_service.authenticate_user("admin@example.com", "StrongPass!123")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["status"], "mfa_required")
        self.assertTrue(result.get("mfa_challenge_token"))

    def test_internal_admin_can_disable_opted_in_mfa(self):
        user_id = ObjectId()
        user = {
            "_id": user_id,
            "email": "admin@example.com",
            "role": "admin",
            "access_tier": "super_admin",
            "password_hash": "stored-password-hash",
            "mfa_enabled": True,
            "mfa_secret_encrypted": "encrypted-secret",
        }
        db = FakeDatabase({"users": [user]})
        with (
            patch.object(auth_service, "verify_password", return_value=True),
            patch.object(auth_service, "_mfa_decrypt_secret", return_value="secret"),
            patch.object(auth_service, "_verify_totp", return_value=True),
            patch.object(auth_service, "get_database", return_value=db),
            patch.object(auth_service, "create_audit_log"),
        ):
            auth_service.disable_mfa_for_user(
                user=user,
                current_password="StrongPass!123",
                code="123456",
                recovery_code=None,
                actor_user_id="admin-1",
            )
        stored = db.users.find_one({"_id": user_id})
        self.assertFalse(stored.get("mfa_enabled"))
        self.assertIsNone(stored.get("mfa_secret_encrypted"))


class AuthDatabaseFailClosedTests(unittest.TestCase):
    def test_login_does_not_issue_token_when_database_is_unavailable(self):
        with patch.object(
            auth_service,
            "get_database",
            side_effect=DatabaseUnavailableError("database unavailable"),
        ):
            with self.assertRaises(DatabaseUnavailableError):
                auth_service.authenticate_user("known@example.com", "Anything!123")

    def test_signup_does_not_claim_success_when_database_is_unavailable(self):
        payload = SimpleNamespace(
            email="new@example.com",
            password="StrongPass!123",
            full_name="New Customer",
            terms_accepted=True,
            privacy_accepted=True,
            eligibility_attested=True,
            policy_version="2026-03-26",
        )
        with patch.object(
            auth_service,
            "get_database",
            side_effect=DatabaseUnavailableError("database unavailable"),
        ):
            with self.assertRaises(DatabaseUnavailableError):
                auth_service.register_user(payload)

    def test_admin_password_reset_is_delivered_without_exposing_raw_token(self):
        user_id = str(ObjectId())
        with (
            patch.object(
                auth_service,
                "get_user_by_id",
                return_value={"_id": ObjectId(user_id), "email": "customer@example.com"},
            ),
            patch.object(
                auth_service,
                "request_password_reset",
                return_value={"success": True, "delivery_mode": "email"},
            ) as request_reset,
        ):
            result = auth_service.admin_issue_password_reset(
                user_id,
                admin_user_id="ceo-1",
                admin_display="CEO Operator",
            )
        self.assertNotIn("reset_token", result)
        request_reset.assert_called_once_with(
            "customer@example.com",
            requested_via="admin_assist",
            requested_by_user_id="ceo-1",
            requested_by="CEO Operator",
            expose_token=False,
            include_delivery_status=True,
        )

    def test_admin_password_reset_reports_delivery_failure_without_exposing_token(self):
        user_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": "customer@example.com",
                    }
                ]
            }
        )
        with (
            patch.object(auth_service, "_get_database_or_none", return_value=db),
            patch.object(auth_service, "create_audit_log"),
            patch.object(
                auth_service,
                "send_password_reset_email",
                return_value={
                    "sent": False,
                    "provider": "postmark",
                    "error": "postmark_token_missing",
                },
            ),
        ):
            result = auth_service.request_password_reset(
                "customer@example.com",
                requested_via="admin_assist",
                include_delivery_status=True,
            )
        self.assertFalse(result["success"])
        self.assertFalse(result["delivery_sent"])
        self.assertEqual(result["failure_count"], 1)
        self.assertNotIn("reset_token", result)
        self.assertTrue(db["users"].documents[0].get("password_reset_token_hash"))


class LinkKeyHardeningTests(unittest.TestCase):
    def test_generate_link_key_stores_hash_only(self):
        db = FakeDatabase({"project_link_keys": []})
        with (
            patch.object(link_key_service, "get_database", return_value=db),
            patch.object(link_key_service, "user_can_access_project", return_value=True),
            patch.object(link_key_service, "project_supports_link_keys", return_value=True),
            patch.object(
                link_key_service,
                "get_project_summary",
                return_value={"package_code": "legacy_plus", "package_name": "Legacy+", "package_lane": "legacy"},
            ),
        ):
            item = link_key_service.generate_link_key(
                project_id="project-1",
                user_id="user-1",
                user_email="user@example.com",
                allow_admin=False,
            )
        self.assertTrue(item["key_value"].startswith("tolk_"))
        stored = db["project_link_keys"].documents[0]
        self.assertIsNone(stored.get("key_value"))
        self.assertTrue(stored.get("key_hash"))


class UploadHardeningTests(unittest.TestCase):
    def test_production_scan_cannot_be_configured_fail_open(self):
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.object(upload_scan_service.settings, "environment", "production"),
            patch.object(upload_scan_service.settings, "upload_scan_fail_closed", False),
            patch.object(upload_scan_service.settings, "upload_scan_hook", ""),
            patch.object(upload_scan_service.settings, "upload_scan_command", ""),
            patch.object(upload_scan_service.settings, "upload_storage_dir", tmpdir),
            patch.object(upload_scan_service.settings, "render_disk_mount_path", ""),
        ):
            file_path = Path(tmpdir) / "pending.pdf"
            file_path.write_bytes(b"pending")
            result = upload_scan_service.scan_uploaded_file(str(file_path))
        self.assertEqual(result.status, "error")

    def test_scan_error_blocks_download_even_if_quarantine_move_failed(self):
        self.assertTrue(
            upload_routes._upload_scan_blocks_download(
                {"scan_status": "error", "quarantined": False}
            )
        )

    def test_scan_and_quarantine_marks_record(self):
        upload_id = ObjectId()
        with tempfile.TemporaryDirectory() as tmpdir:
            upload_root = Path(tmpdir) / "uploads"
            quarantine_root = Path(tmpdir) / "quarantine"
            file_path = upload_root / "verification_evidence" / "sample.pdf"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b"dummy")
            db = FakeDatabase(
                {
                    "uploaded_files": [
                        {
                            "_id": upload_id,
                            "id": str(upload_id),
                            "relative_path": "verification_evidence/sample.pdf",
                        }
                    ]
                }
            )
            with (
                patch.object(upload_routes.settings, "upload_storage_dir", str(upload_root)),
                patch.object(upload_routes.settings, "render_disk_mount_path", ""),
                patch.object(upload_routes.settings, "upload_quarantine_dir", str(quarantine_root)),
                patch.object(upload_routes, "scan_uploaded_file") as scan_mock,
            ):
                scan_mock.return_value = type(
                    "ScanResult",
                    (),
                    {"status": "infected", "detail": "malware_detected"},
                )()
                updated = upload_routes._scan_and_quarantine_upload(
                    db=db,
                    upload_record={"id": str(upload_id), "relative_path": "verification_evidence/sample.pdf"},
                )
            self.assertTrue(updated.get("quarantined"))
            self.assertEqual(updated.get("scan_status"), "infected")


class RootDisclosureTests(unittest.TestCase):
    def test_root_hides_routes_in_production(self):
        from app import main as main_module

        with patch.object(main_module.settings, "environment", "production"):
            payload = main_module.root()
        self.assertNotIn("routes", payload)


if __name__ == "__main__":
    unittest.main()
