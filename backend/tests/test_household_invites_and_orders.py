import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.schemas.household_access import build_invite_response
from app.services import email_service, household_access_service, order_service


class HouseholdInviteAndOrderTests(unittest.TestCase):
    def test_create_household_invite_persists_when_email_delivery_fails(self):
        inserted_docs = []

        class FakeInvitesCollection:
            def insert_one(self, document):
                inserted_docs.append(dict(document))
                return SimpleNamespace(inserted_id="invite-1")

        class FakeMembersCollection:
            def find_one(self, *_args, **_kwargs):
                return None

        actor = {"_id": "owner-1", "email": "owner@example.com"}
        with (
            patch.object(
                household_access_service,
                "_find_project",
                return_value={"_id": "project-1", "owner_user_id": "owner-1", "owner_email": "owner@example.com"},
            ),
            patch.object(household_access_service, "_resolve_actor_role", return_value="billing_owner"),
            patch.object(household_access_service, "_active_member_count", return_value=0),
            patch.object(household_access_service, "_resolve_member_seat_cap", return_value=6),
            patch.object(household_access_service, "_members", return_value=FakeMembersCollection()),
            patch.object(household_access_service, "_invites", return_value=FakeInvitesCollection()),
            patch.object(household_access_service, "create_audit_log"),
            patch.object(
                household_access_service,
                "send_household_invite_email",
                return_value={"sent": False, "error": "Your Postmark account is pending approval."},
            ) as send_email_mock,
        ):
            invite = household_access_service.create_household_invite(
                project_id="project-1",
                actor_user=actor,
                email="wife@example.com",
                member_role="co_owner",
                relationship_scope="spouse",
                privacy_scope="household_private",
            )

        self.assertEqual(len(inserted_docs), 1)
        self.assertEqual(inserted_docs[0]["status"], "pending")
        self.assertTrue(str(inserted_docs[0]["invite_key"]).startswith("hhinv_"))
        self.assertEqual(invite["status"], "pending")
        self.assertEqual(invite["email_delivery_status"], "failed")
        self.assertIn("pending approval", invite["email_delivery_error"])
        send_email_mock.assert_called_once()

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

    def test_household_seat_cap_uses_package_member_limit(self):
        with (
            patch.object(
                household_access_service,
                "get_project_entitlement",
                return_value={"package_code": "legacy_plus", "active_addons": []},
            ),
            patch.object(
                household_access_service,
                "get_package",
                return_value={"package_code": "legacy_plus", "package_lane": "household", "max_members": 30},
            ),
        ):
            self.assertEqual(household_access_service._resolve_member_seat_cap("project-legacy"), 30)


if __name__ == "__main__":
    unittest.main()
