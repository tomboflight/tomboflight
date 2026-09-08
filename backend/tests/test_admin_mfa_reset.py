import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException
from starlette.responses import Response

from app.routes import auth as auth_routes
from app.schemas.auth import AdminMfaResetRequest
from app.services import auth_service


class _UsersCollection:
    def __init__(self, *, matched_count: int = 1):
        self.matched_count = matched_count
        self.last_query = None
        self.last_update = None

    def update_one(self, query, update):
        self.last_query = query
        self.last_update = update
        return SimpleNamespace(matched_count=self.matched_count)


class _Database:
    def __init__(self, users):
        self.users = users


class AdminMfaResetTests(unittest.TestCase):
    def test_admin_reset_user_mfa_supports_email_lookup_and_clears_fields(self):
        user_id = ObjectId()
        user = {
            "_id": user_id,
            "email": "Locked.Admin@example.com",
            "session_token_version": 4,
            "mfa_enabled": True,
            "mfa_secret_encrypted": "ciphertext",
            "mfa_backup_code_hashes": ["hash-1"],
            "mfa_enrolled_at": "2026-09-01T00:00:00+00:00",
            "mfa_last_verified_at": "2026-09-02T00:00:00+00:00",
            "mfa_pending_secret_encrypted": "pending",
            "mfa_pending_started_at": "2026-09-03T00:00:00+00:00",
        }
        users = _UsersCollection()
        db = _Database(users)

        with (
            patch.object(auth_service, "get_user_by_email", return_value=user) as get_by_email,
            patch.object(auth_service, "get_database", return_value=db),
            patch.object(auth_service, "create_audit_log") as audit_log,
        ):
            result = auth_service.admin_reset_user_mfa(
                target_email="LOCKED.ADMIN@example.com",
                actor_user_id="admin-user-1",
                actor_email="operations-admin@example.com",
            )

        self.assertEqual(result, {"user_id": str(user_id), "email": "locked.admin@example.com"})
        get_by_email.assert_called_once_with("locked.admin@example.com")
        self.assertEqual(
            users.last_query,
            {"_id": user_id, "session_token_version": 4},
        )
        update_fields = users.last_update["$set"]
        self.assertFalse(update_fields["mfa_enabled"])
        self.assertIsNone(update_fields["mfa_secret_encrypted"])
        self.assertEqual(update_fields["mfa_backup_code_hashes"], [])
        self.assertIsNone(update_fields["mfa_enrolled_at"])
        self.assertIsNone(update_fields["mfa_last_verified_at"])
        self.assertIsNone(update_fields["mfa_pending_secret_encrypted"])
        self.assertIsNone(update_fields["mfa_pending_started_at"])
        self.assertEqual(update_fields["session_token_version"], 5)
        self.assertEqual(update_fields["updated_by"], "admin-user-1")
        self.assertTrue(update_fields["updated_at"])
        self.assertTrue(update_fields["last_logout_at"])
        audit_log.assert_called_once_with(
            "admin_security_reset",
            "admin-user-1",
            "user",
            str(user_id),
            {
                "email": "locked.admin@example.com",
                "lookup_mode": "email",
                "reset_scope": "mfa",
            },
        )

    def test_admin_mfa_reset_route_returns_safe_success_payload(self):
        response = Response()
        current_user = {"id": "admin-user-1", "email": "operations-admin@example.com"}
        payload = AdminMfaResetRequest(email="locked.admin@example.com")

        with patch.object(
            auth_routes,
            "admin_reset_user_mfa",
            return_value={"user_id": "user-123", "email": "locked.admin@example.com"},
        ) as reset_mfa:
            result = auth_routes.admin_mfa_reset_route(
                payload=payload,
                response=response,
                current_user=current_user,
            )

        self.assertEqual(
            result,
            {
                "success": True,
                "message": "Authenticator MFA reset successfully.",
                "user_id": "user-123",
                "email": "locked.admin@example.com",
            },
        )
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        reset_mfa.assert_called_once_with(
            target_user_id="",
            target_email="locked.admin@example.com",
            actor_user_id="admin-user-1",
            actor_email="operations-admin@example.com",
        )

    def test_admin_mfa_reset_route_requires_target_identifier(self):
        response = Response()
        current_user = {"id": "admin-user-1", "email": "operations-admin@example.com"}
        payload = AdminMfaResetRequest()

        with patch.object(
            auth_routes,
            "admin_reset_user_mfa",
            side_effect=ValueError("Target user email or user id is required."),
        ):
            with self.assertRaises(HTTPException) as error:
                auth_routes.admin_mfa_reset_route(
                    payload=payload,
                    response=response,
                    current_user=current_user,
                )

        self.assertEqual(error.exception.status_code, 400)
        self.assertEqual(error.exception.detail, "Target user email or user id is required.")


if __name__ == "__main__":
    unittest.main()
