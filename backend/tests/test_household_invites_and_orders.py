import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.schemas.household_access import build_invite_response
from app.services import email_service, order_service


class HouseholdInviteAndOrderTests(unittest.TestCase):
    def test_build_invite_response_includes_expired_timestamp(self):
        payload = build_invite_response(
            {
                "_id": "invite-1",
                "project_id": "project-1",
                "email": "member@example.com",
                "status": "expired",
                "member_role": "viewer",
                "expires_at": "2026-04-10T00:00:00Z",
                "expired_at": "2026-04-11T00:00:00Z",
            }
        )
        self.assertEqual(payload["status"], "expired")
        self.assertEqual(payload["expired_at"], "2026-04-11T00:00:00Z")

    def test_household_invite_email_uses_workspace_accept_link(self):
        with (
            patch.object(email_service, "_public_app_base_url", return_value="https://tomboflight.com"),
            patch.object(email_service, "_send_email") as send_mock,
        ):
            email_service.send_household_invite_email(
                to_email="invitee@example.com",
                invite_key="hhinv_abc123",
                project_id="project-123",
                member_role="co_owner",
                inviter_email="owner@example.com",
            )

        send_mock.assert_called_once()
        kwargs = send_mock.call_args.kwargs
        self.assertEqual(kwargs["to_email"], "invitee@example.com")
        self.assertIn("household-access.html", kwargs["text_body"])
        self.assertIn("household-access.html", kwargs["html_body"])

    def test_duplicate_workspace_package_checkout_is_rejected(self):
        payload = SimpleNamespace(
            package_code="legacy_plus",
            package_slug=None,
            package_name="Legacy Plus",
            price_label="$399",
            item_type="package",
            billing_plan="one_time",
            source="stripe_verified",
            order_status="paid",
            project_id="507f1f77bcf86cd799439011",
            stripe_session_id=None,
            stripe_payment_link_id=None,
        )
        user = {"_id": "507f1f77bcf86cd799439012", "email": "invitee@example.com"}
        with (
            patch.object(order_service, "_get_orders_collection", return_value=object()),
            patch.object(
                order_service,
                "get_project_entitlement",
                return_value={"status": "active", "package_code": "legacy_plus"},
            ),
        ):
            with self.assertRaises(ValueError) as error:
                order_service.create_order_for_user(user, payload)
        self.assertIn("Invite members instead of purchasing again", str(error.exception))


if __name__ == "__main__":
    unittest.main()
