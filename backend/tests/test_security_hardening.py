import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException

from app.core.security import create_csrf_token, verify_csrf_token
from app.routes import uploads as upload_routes
from app.services import auth_service, link_key_service, rate_limit_service


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
    def test_internal_admin_without_mfa_can_authenticate(self):
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
                        "mfa_enabled": False,
                        "session_token_version": 0,
                    }
                ]
            }
        )
        with patch.object(auth_service, "_get_database_or_none", return_value=db):
            result = auth_service.authenticate_user("admin@example.com", "StrongPass!123")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["status"], "authenticated")
        self.assertTrue(result.get("access_token"))

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
                        "mfa_enabled": True,
                        "session_token_version": 0,
                    }
                ]
            }
        )
        with patch.object(auth_service, "_get_database_or_none", return_value=db):
            result = auth_service.authenticate_user("admin@example.com", "StrongPass!123")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["status"], "mfa_required")
        self.assertTrue(result.get("mfa_challenge_token"))


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
