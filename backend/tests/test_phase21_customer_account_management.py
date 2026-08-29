from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bson import ObjectId

from app.services import billing_service, user_service


class _UsersCollection:
    def __init__(self, user: dict):
        self.user = deepcopy(user)

    def find_one(self, query, projection=None):
        del projection
        expected_status = query.get("status")
        if isinstance(expected_status, dict) and "$nin" in expected_status:
            if self.user.get("status") in expected_status["$nin"]:
                return None
        if "stripe_customer_id" in query:
            return (
                deepcopy(self.user)
                if self.user.get("stripe_customer_id") == query["stripe_customer_id"]
                else None
            )
        if "pending_email_change_token_hash" in query:
            return (
                deepcopy(self.user)
                if self.user.get("pending_email_change_token_hash")
                == query["pending_email_change_token_hash"]
                else None
            )
        if "email" in query:
            expected = query["email"]
            if isinstance(expected, str):
                return deepcopy(self.user) if self.user.get("email") == expected else None
            return None
        expected_id = query.get("_id")
        return deepcopy(self.user) if expected_id == self.user.get("_id") else None

    def update_one(self, query, update, **kwargs):
        del kwargs
        existing = self.find_one(query)
        if existing is None:
            return SimpleNamespace(matched_count=0, modified_count=0)
        for key, value in (update.get("$set") or {}).items():
            self.user[key] = value
        for key in (update.get("$unset") or {}):
            self.user.pop(key, None)
        for key, value in (update.get("$addToSet") or {}).items():
            values = list(self.user.get(key) or [])
            if value not in values:
                values.append(value)
            self.user[key] = values
        return SimpleNamespace(matched_count=1, modified_count=1)


class _Database:
    def __init__(self, user: dict):
        self.users = _UsersCollection(user)

    def get_collection(self, name: str):
        assert name == "users"
        return self.users


class Phase21CustomerAccountManagementTests(unittest.TestCase):
    def setUp(self):
        self.user_id = ObjectId()
        self.user = {
            "_id": self.user_id,
            "email": "customer@example.com",
            "full_name": "Customer Name",
            "password_hash": "hash",
            "session_token_version": 2,
            "stripe_customer_id": "cus_123",
        }

    def test_profile_update_normalizes_contact_and_preserves_structured_address(self):
        database = _Database(self.user)
        with (
            patch.object(user_service, "get_database", return_value=database),
            patch.object(user_service, "write_audit_log"),
            patch.object(billing_service, "sync_account_contact_to_stripe") as sync_stripe,
        ):
            updated = user_service.update_user_profile(
                str(self.user_id),
                full_name="Customer Updated",
                phone_number="(912) 555-0123",
                mailing_address={
                    "line1": "100 Main Street",
                    "line2": "Suite 2",
                    "city": "Savannah",
                    "region": "GA",
                    "postal_code": "31401",
                    "country": "us",
                },
            )

        assert updated is not None
        self.assertEqual(updated["phone_number"], "+19125550123")
        self.assertEqual(updated["mailing_address_structured"]["country"], "US")
        self.assertEqual(updated["billing_profile_sync_status"], "synced")
        sync_stripe.assert_called_once()

    def test_profile_update_records_pending_when_stripe_sync_fails(self):
        database = _Database(self.user)
        with (
            patch.object(user_service, "get_database", return_value=database),
            patch.object(user_service, "write_audit_log"),
            patch.object(
                billing_service,
                "sync_account_contact_to_stripe",
                side_effect=RuntimeError("stripe unavailable"),
            ),
        ):
            updated = user_service.update_user_profile(
                str(self.user_id),
                full_name="Customer Name",
                phone_number=None,
                mailing_address=None,
            )

        assert updated is not None
        self.assertEqual(updated["billing_profile_sync_status"], "pending")

    def test_email_change_requires_password_and_verifies_new_mailbox(self):
        database = _Database(self.user)
        with (
            patch.object(user_service, "get_database", return_value=database),
            patch("app.services.auth_service.verify_password", return_value=True),
            patch.object(user_service, "write_audit_log"),
            patch.object(
                user_service,
                "send_email_change_verification_email",
                return_value={"sent": True},
            ) as send_verification,
        ):
            result = user_service.request_email_change(
                str(self.user_id),
                new_email="new@example.com",
                current_password="CurrentPassword!123",
            )

        self.assertTrue(result["success"])
        self.assertEqual(database.users.user["pending_email"], "new@example.com")
        self.assertNotIn("token", result)
        verification_url = send_verification.call_args.kwargs["verification_url"]
        self.assertIn("#mode=email-change&token=", verification_url)

    def test_email_confirmation_changes_login_revokes_sessions_and_preserves_alias(self):
        token = "phase21-email-change-token"
        self.user.update(
            {
                "pending_email": "new@example.com",
                "pending_email_change_token_hash": user_service._email_change_token_hash(token),
                "pending_email_change_expires_at": "2999-01-01T00:00:00+00:00",
            }
        )
        database = _Database(self.user)
        with (
            patch.object(user_service, "get_database", return_value=database),
            patch.object(user_service, "write_audit_log"),
            patch.object(user_service, "send_email_changed_notice"),
            patch.object(billing_service, "sync_verified_email_to_stripe"),
        ):
            result = user_service.confirm_email_change(token)

        self.assertTrue(result["success"])
        self.assertEqual(database.users.user["email"], "new@example.com")
        self.assertEqual(database.users.user["session_token_version"], 3)
        self.assertIn("customer@example.com", database.users.user["email_aliases"])
        self.assertNotIn("pending_email_change_token_hash", database.users.user)

    def test_email_confirmation_cannot_reactivate_a_deletion_locked_identity(self):
        token = "phase21-deleted-email-change-token"
        self.user.update(
            {
                "status": "deletion_in_progress",
                "login_enabled": False,
                "pending_email": "new@example.com",
                "pending_email_change_token_hash": user_service._email_change_token_hash(token),
                "pending_email_change_expires_at": "2999-01-01T00:00:00+00:00",
            }
        )
        database = _Database(self.user)

        with patch.object(user_service, "get_database", return_value=database):
            with self.assertRaisesRegex(ValueError, "invalid, expired, or already used"):
                user_service.confirm_email_change(token)

        self.assertEqual(database.users.user["email"], "customer@example.com")
        self.assertEqual(database.users.user["status"], "deletion_in_progress")

    def test_stripe_customer_webhook_cannot_change_login_email(self):
        database = _Database(self.user)
        event = {
            "data": {
                "object": {
                    "id": "cus_123",
                    "email": "billing@example.com",
                    "name": "Billing Name",
                    "phone": "+19125550123",
                    "address": {"line1": "10 Billing Way", "country": "US"},
                }
            }
        }
        with (
            patch.object(billing_service, "get_database", return_value=database),
            patch.object(billing_service, "create_audit_log"),
        ):
            result = billing_service.sync_billing_customer_updated_event(event)

        self.assertTrue(result["updated"])
        self.assertEqual(database.users.user["email"], "customer@example.com")
        self.assertEqual(database.users.user["billing_contact"]["email"], "billing@example.com")

    def test_customer_ui_exposes_structured_profile_and_verified_email_controls(self):
        root = Path(__file__).resolve().parents[2]
        billing_html = (root / "billing.html").read_text(encoding="utf-8")
        billing_js = (root / "billing.js").read_text(encoding="utf-8")
        dashboard_html = (root / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn("data-account-details-form", billing_html)
        self.assertIn('autocomplete="address-line1"', billing_html)
        self.assertIn("data-email-change-form", billing_html)
        self.assertIn('"/users/me/profile"', billing_js)
        self.assertIn('"/users/me/email-change/request"', billing_js)
        self.assertIn("billing.html#personal-details", dashboard_html)


if __name__ == "__main__":
    unittest.main()
