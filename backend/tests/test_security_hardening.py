import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException
from starlette.requests import Request

from app.core import continuity_route_guard, security as security_core
from app.core.security import create_csrf_token, verify_csrf_token
from app.database import DatabaseUnavailableError
from app.routes import auth as auth_routes
from app.routes import uploads as upload_routes
from app.schemas.auth import UserCreate as AuthUserCreate
from app.services import (
    auth_service,
    link_key_service,
    poster_asset_service,
    rate_limit_service,
    upload_scan_service,
)


class FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeUpdateResult:
    def __init__(self, matched_count=0, modified_count=0):
        self.matched_count = matched_count
        self.modified_count = modified_count


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])
        self.indexes = {}

    def create_index(self, keys, **options):
        name = options.get("name") or str(keys)
        self.indexes[name] = {"keys": keys, **options}
        return name

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
            return FakeUpdateResult()
        item.update(update.get("$set", {}))
        for key, expected in update.get("$pull", {}).items():
            values = list(item.get(key) or [])
            item[key] = [value for value in values if value != expected]
        for key in update.get("$unset", {}):
            item.pop(key, None)
        return FakeUpdateResult(matched_count=1, modified_count=1)

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
            elif isinstance(value, list):
                if expected not in value:
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

    def test_rate_limit_identity_does_not_trust_spoofed_forwarded_address(self):
        request = Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "POST",
                "path": "/auth/login",
                "headers": [(b"x-forwarded-for", b"198.51.100.44")],
                "query_string": b"",
                "client": ("203.0.113.25", 50000),
                "scheme": "https",
                "server": ("testserver", 443),
            }
        )
        self.assertEqual(
            auth_routes._rate_key_from_request(
                request, principal="Customer@Example.com"
            ),
            "203.0.113.25:customer@example.com",
        )


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


    def test_stale_mfa_challenge_is_rejected_after_session_revocation(self):
        user_id = ObjectId()
        user = {
            "_id": user_id,
            "email": "admin@example.com",
            "status": "active",
            "mfa_enabled": True,
            "session_token_version": 7,
        }
        with (
            patch.object(
                auth_service,
                "decode_access_token",
                return_value={
                    "purpose": "mfa_login",
                    "sub": "admin@example.com",
                    "user_id": str(user_id),
                    "tv": 1,
                },
            ),
            patch.object(auth_service, "get_user_by_email", return_value=user),
        ):
            with self.assertRaisesRegex(ValueError, "Invalid MFA challenge token"):
                auth_service.verify_mfa_login_challenge(
                    "stale-challenge",
                    code="123456",
                )

    def test_recovery_code_is_consumed_with_an_atomic_pull(self):
        user_id = ObjectId()
        recovery_code = "single-use-recovery"
        recovery_hash = auth_service._hash_recovery_code(
            recovery_code,
            user_id=str(user_id),
        )
        stored_user = {
            "_id": user_id,
            "email": "admin@example.com",
            "mfa_backup_code_hashes": [recovery_hash],
        }
        stale_snapshot = {
            **stored_user,
            "mfa_backup_code_hashes": [recovery_hash],
        }
        db = FakeDatabase({"users": [stored_user]})
        with patch.object(auth_service, "get_database", return_value=db):
            self.assertTrue(
                auth_service._consume_recovery_code(
                    stale_snapshot,
                    recovery_code,
                )
            )
            self.assertFalse(
                auth_service._consume_recovery_code(
                    stale_snapshot,
                    recovery_code,
                )
            )

    def test_password_reset_url_keeps_token_out_of_query_string(self):
        reset_url = auth_service._build_password_reset_url(
            "reset-token-that-must-not-enter-http-logs"
        )
        self.assertIn("#mode=reset&token=", reset_url)
        self.assertNotIn("?mode=reset", reset_url)

    def test_password_reset_compare_and_set_rejects_a_lost_token_race(self):
        token = "single-use-password-reset-token"
        user = {
            "_id": ObjectId(),
            "email": "customer@example.com",
            "status": "active",
            "session_token_version": 3,
            "password_reset_token_hash": auth_service._hash_password_reset_token(token),
            "password_reset_expires_at": "2999-01-01T00:00:00+00:00",
        }

        class ContendedUsers:
            def find_one(self, query):
                del query
                return dict(user)

            def update_one(self, query, update):
                del query, update
                return FakeUpdateResult(matched_count=0, modified_count=0)

        class ContendedDatabase:
            users = ContendedUsers()

        with patch.object(auth_service, "get_database", return_value=ContendedDatabase()):
            with self.assertRaisesRegex(ValueError, "already used"):
                auth_service.reset_password_with_token(
                    token,
                    "NewStrongPassword!123",
                )


class PosterPublicationGateTests(unittest.TestCase):
    def test_uploaded_portrait_query_requires_scan_approval_and_consent(self):
        class CapturingUploads:
            query = None

            def find_one(self, query, sort=None):
                self.query = query
                self.sort = sort
                return None

        uploads = CapturingUploads()
        with patch.object(
            poster_asset_service,
            "_uploads_collection",
            return_value=uploads,
        ):
            self.assertIsNone(
                poster_asset_service._best_uploaded_portrait("project-1")
            )

        self.assertEqual(uploads.query["scan_status"], "clean")
        self.assertEqual(uploads.query["quarantined"], {"$ne": True})
        self.assertTrue(uploads.query["approved_for_cinematic"])
        self.assertEqual(uploads.query["verification_status"], "approved")
        self.assertEqual(uploads.query["consent_status"], "approved")


class AccountActivationSecurityTests(unittest.TestCase):
    def _payload(self, *, email: str, activation_token: str | None = None) -> AuthUserCreate:
        return AuthUserCreate(
            email=email,
            password="StrongActivationPass!123",
            full_name="Activation Customer",
            terms_accepted=True,
            privacy_accepted=True,
            eligibility_attested=True,
            policy_version="2026-03-26",
            activation_token=activation_token,
        )

    def test_new_public_signup_stays_passwordless_until_email_activation(self):
        db = FakeDatabase({"users": []})
        raw_token = "activation-token-that-is-never-stored-raw"
        with (
            patch.object(auth_service, "get_database", return_value=db),
            patch.object(auth_service.secrets, "token_urlsafe", return_value=raw_token),
            patch.object(
                auth_service,
                "send_account_activation_email",
                return_value={"sent": True, "provider": "postmark"},
            ) as send_activation,
            patch.object(auth_service, "create_audit_log"),
        ):
            user = auth_service.register_user(
                self._payload(email="new.activation@example.com")
            )

        self.assertIsNotNone(user)
        assert user is not None
        self.assertEqual(user["status"], "pending_activation")
        self.assertTrue(user["requires_account_activation"])
        self.assertIsNone(user["password_hash"])
        self.assertNotIn(raw_token, str(db.users.documents))
        self.assertEqual(
            user["account_activation_token_hash"],
            auth_service._hash_account_activation_token(raw_token),
        )
        activation_url = send_activation.call_args.kwargs["activation_url"]
        self.assertIn("#activation_token=", activation_url)
        self.assertNotIn("?activation_token=", activation_url)

    def test_identity_startup_indexes_enforce_unique_email_and_live_activation_token(self):
        db = FakeDatabase({"users": []})
        with patch.object(auth_service, "get_database", return_value=db):
            auth_service.ensure_auth_indexes()

        email_index = db.users.indexes["idx_users_email_unique"]
        activation_index = db.users.indexes[
            "idx_users_activation_token_hash_unique"
        ]
        self.assertTrue(email_index["unique"])
        self.assertTrue(activation_index["unique"])
        self.assertEqual(
            activation_index["partialFilterExpression"],
            {"account_activation_token_hash": {"$type": "string"}},
        )

    def test_pending_account_cannot_be_claimed_without_the_live_activation_token(self):
        user_id = ObjectId()
        raw_token = "valid-activation-token-value"
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": "pending@example.com",
                        "full_name": "Pending Customer",
                        "role": "user",
                        "account_type": "customer",
                        "status": "pending_activation",
                        "password_hash": None,
                        "session_token_version": 0,
                        "account_activation_token_hash": auth_service._hash_account_activation_token(
                            raw_token
                        ),
                        "account_activation_expires_at": (
                            datetime.now(UTC) + timedelta(hours=1)
                        ).isoformat(),
                        "created_at": datetime.now(UTC).isoformat(),
                    }
                ]
            }
        )

        with patch.object(auth_service, "get_database", return_value=db):
            missing = auth_service.register_user(
                self._payload(email="pending@example.com")
            )
            invalid = auth_service.register_user(
                self._payload(
                    email="pending@example.com",
                    activation_token="invalid-activation-token",
                )
            )
            activated = auth_service.register_user(
                self._payload(
                    email="pending@example.com",
                    activation_token=raw_token,
                )
            )
            replay = auth_service.register_user(
                self._payload(
                    email="pending@example.com",
                    activation_token=raw_token,
                )
            )

        self.assertIsNone(missing)
        self.assertIsNone(invalid)
        self.assertIsNotNone(activated)
        assert activated is not None
        self.assertEqual(activated["status"], "active")
        self.assertTrue(
            auth_service.verify_password(
                "StrongActivationPass!123", activated["password_hash"]
            )
        )
        self.assertIsNone(activated["account_activation_token_hash"])
        self.assertIsNone(replay)

    def test_signup_browser_consumes_activation_from_fragment_and_clears_it(self):
        repository_root = Path(__file__).resolve().parents[2]
        auth_source = (repository_root / "auth.js").read_text(encoding="utf-8")
        signup_source = (repository_root / "signup.html").read_text(encoding="utf-8")
        self.assertIn("window.location.hash", auth_source)
        self.assertIn("activation_token", auth_source)
        self.assertIn("window.history.replaceState", auth_source)
        self.assertNotIn("Email verified. Enter your account details", auth_source)
        self.assertIn("auth.js?v=20260822-phase11", signup_source)


class ContinuityLegacyRouteGuardTests(unittest.TestCase):
    def test_covered_legacy_mutations_require_kernel_execution(self):
        for method, path in (
            ("POST", "/admin/control-center/super-admin/users"),
            ("POST", "/admin/control-center/super-admin/legacy-admin-review"),
            ("PATCH", "/admin/control-center/super-admin/users/user-1"),
            ("POST", "/admin/stripe-ops/subscriptions/cancel"),
            ("POST", "/auth/admin/users/user-1/password-reset"),
            ("POST", "/orders/admin/manual-order"),
            ("POST", "/orders/admin/repair-paid-package-access"),
            ("POST", "/project-entitlements/apply"),
            ("POST", "/users"),
        ):
            with self.subTest(method=method, path=path):
                self.assertTrue(
                    continuity_route_guard.requires_continuity_kernel(method, path)
                )

    def test_reads_previews_and_kernel_execution_remain_available(self):
        for method, path in (
            ("GET", "/admin/control-center/super-admin/users"),
            ("POST", "/admin/control-center/super-admin/users/preview"),
            ("POST", "/admin/control-center/kernel/execute"),
            ("GET", "/admin/stripe-ops/customers/history"),
            ("PATCH", "/users/me/profile"),
        ):
            with self.subTest(method=method, path=path):
                self.assertFalse(
                    continuity_route_guard.requires_continuity_kernel(method, path)
                )


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

    def test_permanently_deleted_identity_cannot_receive_password_reset(self):
        user_id = ObjectId()
        db = FakeDatabase(
            {
                "users": [
                    {
                        "_id": user_id,
                        "email": f"deleted+{user_id}@accounts.invalid",
                        "status": "permanently_deleted",
                        "account_type": "deleted_tombstone",
                    }
                ]
            }
        )
        with (
            patch.object(auth_service, "_get_database_or_none", return_value=db),
            patch.object(auth_service, "send_password_reset_email") as send_reset,
        ):
            result = auth_service.request_password_reset(
                f"deleted+{user_id}@accounts.invalid",
                requested_via="admin_assist",
                include_delivery_status=True,
            )

        self.assertFalse(result["success"])
        self.assertFalse(result["reset_persisted"])
        self.assertFalse(result["delivery_sent"])
        self.assertEqual(result["delivery_error"], "account_not_active")
        self.assertNotIn("password_reset_token_hash", db["users"].documents[0])
        send_reset.assert_not_called()

    def test_admin_cannot_issue_reset_for_permanently_deleted_identity(self):
        user_id = str(ObjectId())
        with (
            patch.object(
                auth_service,
                "get_user_by_id",
                return_value={
                    "_id": ObjectId(user_id),
                    "email": f"deleted+{user_id}@accounts.invalid",
                    "status": "permanently_deleted",
                    "account_type": "deleted_tombstone",
                },
            ),
            patch.object(auth_service, "request_password_reset") as request_reset,
        ):
            with self.assertRaisesRegex(ValueError, "permanently deleted"):
                auth_service.admin_issue_password_reset(
                    user_id,
                    admin_user_id="ceo-1",
                    admin_display="CEO Operator",
                )
        request_reset.assert_not_called()


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
