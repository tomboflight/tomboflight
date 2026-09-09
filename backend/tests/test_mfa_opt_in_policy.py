import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.dependencies import auth as auth_dependencies
from app.services import auth_service, presence_service


class _UsersCollection:
    def __init__(self, user):
        self.user = user
        self.last_update = None

    def find_one(self, query):
        if query.get("email") == self.user.get("email"):
            return self.user
        return None

    def update_one(self, query, update):
        self.last_update = (query, update)
        return SimpleNamespace(matched_count=1)


class _Database:
    def __init__(self, user):
        self.users = _UsersCollection(user)


class MfaOptInPolicyTests(unittest.TestCase):
    def _admin_user(self, *, mfa_enabled: bool) -> dict:
        return {
            "_id": "admin-1",
            "id": "admin-1",
            "user_id": "admin-1",
            "email": "admin@example.test",
            "status": "active",
            "account_type": "internal_admin",
            "role": "ceo",
            "role_codes": ["ceo"],
            "password_hash": "password-hash",
            "session_token_version": 0,
            "mfa_enabled": mfa_enabled,
        }

    def test_admin_with_mfa_disabled_authenticates_with_password_without_forced_enrollment(self):
        user = self._admin_user(mfa_enabled=False)
        db = _Database(user)

        with (
            patch.object(auth_service, "get_database", return_value=db),
            patch.object(auth_service, "verify_password", return_value=True),
            patch.object(auth_service, "_build_access_token_for_user", return_value="admin-token") as build_token,
            patch.object(auth_service, "create_access_token") as challenge_token,
        ):
            result = auth_service.authenticate_user(user["email"], "correct-password")

        self.assertEqual(
            result,
            {"status": "authenticated", "access_token": "admin-token"},
        )
        build_token.assert_called_once_with(user)
        challenge_token.assert_not_called()
        self.assertIsNotNone(db.users.last_update)
        update_fields = db.users.last_update[1]["$set"]
        self.assertIsNone(update_fields["mfa_pending_secret_encrypted"])
        self.assertIsNone(update_fields["mfa_pending_started_at"])

    def test_admin_with_mfa_enabled_still_requires_mfa_login_challenge(self):
        user = self._admin_user(mfa_enabled=True)
        db = _Database(user)

        with (
            patch.object(auth_service, "get_database", return_value=db),
            patch.object(auth_service, "verify_password", return_value=True),
            patch.object(auth_service, "create_access_token", return_value="mfa-challenge") as challenge_token,
            patch.object(auth_service, "_build_access_token_for_user") as build_token,
        ):
            result = auth_service.authenticate_user(user["email"], "correct-password")

        self.assertEqual(
            result,
            {"status": "mfa_required", "mfa_challenge_token": "mfa-challenge"},
        )
        challenge_token.assert_called_once()
        build_token.assert_not_called()

    def test_privileged_session_is_allowed_when_mfa_is_disabled(self):
        user = self._admin_user(mfa_enabled=False)
        payload = {
            "sub": user["email"],
            "user_id": user["id"],
            "tv": 0,
        }

        with (
            patch.object(auth_dependencies, "_get_token_from_request", return_value=("token", "bearer")),
            patch.object(auth_dependencies, "decode_access_token", return_value=payload),
            patch.object(auth_dependencies, "get_user_by_email", return_value=user),
        ):
            resolved = auth_dependencies.get_current_user(request=object(), credentials=None)

        self.assertEqual(resolved["id"], "admin-1")
        self.assertFalse(resolved["mfa_enabled"])

    def test_enabled_mfa_still_requires_verified_session_claim(self):
        user = self._admin_user(mfa_enabled=True)
        payload = {
            "sub": user["email"],
            "user_id": user["id"],
            "tv": 0,
        }

        with (
            patch.object(auth_dependencies, "_get_token_from_request", return_value=("token", "bearer")),
            patch.object(auth_dependencies, "decode_access_token", return_value=payload),
            patch.object(auth_dependencies, "get_user_by_email", return_value=user),
        ):
            with self.assertRaises(HTTPException) as error:
                auth_dependencies.get_current_user(request=object(), credentials=None)

        self.assertEqual(error.exception.status_code, 401)
        self.assertEqual(error.exception.detail, "MFA verification is required for this session.")

    def test_privileged_websocket_session_is_allowed_when_mfa_is_disabled(self):
        user = self._admin_user(mfa_enabled=False)
        payload = {
            "sub": user["email"],
            "user_id": user["id"],
            "tv": 0,
        }

        with (
            patch.object(presence_service, "decode_access_token", return_value=payload),
            patch.object(presence_service, "get_user_by_id", return_value=user),
        ):
            resolved = presence_service.authenticate_presence_user("token")

        self.assertEqual(resolved["id"], "admin-1")

    def test_enabled_mfa_still_requires_verified_websocket_claim(self):
        user = self._admin_user(mfa_enabled=True)
        payload = {
            "sub": user["email"],
            "user_id": user["id"],
            "tv": 0,
        }

        with (
            patch.object(presence_service, "decode_access_token", return_value=payload),
            patch.object(presence_service, "get_user_by_id", return_value=user),
        ):
            with self.assertRaises(HTTPException) as error:
                presence_service.authenticate_presence_user("token")

        self.assertEqual(error.exception.status_code, 401)
        self.assertEqual(
            error.exception.detail,
            "MFA verification is required for this websocket session.",
        )

    def test_account_security_ui_presents_mfa_as_optional(self):
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[2]
        source = (repo_root / "account-security.js").read_text(encoding="utf-8")
        self.assertIn(
            "Authenticator verification is optional. You can enable it here whenever you want an extra sign-in step.",
            source,
        )
        self.assertIn('"/auth/mfa/disable"', source)


if __name__ == "__main__":
    unittest.main()
