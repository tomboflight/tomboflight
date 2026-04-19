import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.schemas.household_access import build_invite_response
from app.services import email_service, household_access_service, order_service


class HouseholdInviteAndOrderTests(unittest.TestCase):
    def test_create_household_invite_persists_when_email_delivery_fails(self):
        inserted_docs = []

        class FakeInvitesCollection:
            def __init__(self):
                self.updated = []

            def insert_one(self, document):
                inserted_docs.append(dict(document))
                return SimpleNamespace(inserted_id="invite-1")

            def update_one(self, _query, update):
                self.updated.append(update.get("$set") or {})

        class FakeMembersCollection:
            def find_one(self, *_args, **_kwargs):
                return None

        actor = {"_id": "owner-1", "email": "owner@example.com"}
        fake_invites = FakeInvitesCollection()
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
            patch.object(household_access_service, "_invites", return_value=fake_invites),
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
        self.assertEqual(fake_invites.updated[-1]["email_delivery_status"], "failed")
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

    def test_accept_household_invite_sets_user_active_project_context(self):
        now_iso = "2026-04-16T12:00:00+00:00"
        invite_document = {
            "_id": "invite-accept-1",
            "invite_key": "hhinv_accept_key",
            "status": "pending",
            "project_id": "project-accept-1",
            "email": "invitee@example.com",
            "member_role": "spouse",
            "relationship_scope": "spouse",
            "privacy_scope": "household_private",
            "use_count": 0,
            "max_uses": 1,
        }

        class FakeInvitesCollection:
            def __init__(self, invite):
                self.invite = dict(invite)

            def find_one(self, query):
                if query.get("invite_key") == self.invite.get("invite_key"):
                    return dict(self.invite)
                if query.get("_id") == self.invite.get("_id"):
                    return dict(self.invite)
                return None

            def update_one(self, query, update):
                if query.get("_id") != self.invite.get("_id"):
                    return
                updates = update.get("$set") or {}
                self.invite.update(updates)

        class FakeMembersCollection:
            def __init__(self):
                self.member = {}

            def update_one(self, _query, update, upsert=False):
                updates = update.get("$set") or {}
                self.member.update(updates)
                self.member.setdefault("_id", "membership-accept-1")
                if upsert and "$setOnInsert" in update:
                    for key, value in (update.get("$setOnInsert") or {}).items():
                        self.member.setdefault(key, value)

            def find_one(self, _query):
                return dict(self.member)

        class FakeUsersCollection:
            def __init__(self):
                self.updates = []

            def update_one(self, query, update):
                self.updates.append(
                    {
                        "query": dict(query),
                        "update": dict(update),
                    }
                )

        fake_invites = FakeInvitesCollection(invite_document)
        fake_members = FakeMembersCollection()
        fake_users = FakeUsersCollection()
        fake_db = {"users": fake_users}

        with (
            patch.object(household_access_service, "_invites", return_value=fake_invites),
            patch.object(household_access_service, "_members", return_value=fake_members),
            patch.object(household_access_service, "_db", return_value=fake_db),
            patch.object(
                household_access_service,
                "_now",
                return_value=SimpleNamespace(isoformat=lambda: now_iso),
            ),
            patch.object(
                household_access_service,
                "_active_member_count",
                return_value=0,
            ),
            patch.object(
                household_access_service,
                "_resolve_member_seat_cap",
                return_value=10,
            ),
            patch.object(household_access_service, "create_audit_log"),
        ):
            membership = household_access_service.accept_household_invite(
                invite_key="hhinv_accept_key",
                user={"id": "user-accept-1", "email": "invitee@example.com"},
            )

        self.assertEqual(membership.get("project_id"), "project-accept-1")
        self.assertEqual(membership.get("member_role"), "co_owner")
        self.assertEqual(len(fake_users.updates), 1)
        user_update = fake_users.updates[0]["update"]["$set"]
        self.assertEqual(user_update.get("active_project_id"), "project-accept-1")
        self.assertEqual(user_update.get("active_project_selected_at"), now_iso)

    def test_delete_household_invite_removes_non_pending_history_record(self):
        invite_document = {
            "_id": "invite-delete-1",
            "project_id": "project-delete-1",
            "status": "revoked",
        }

        class FakeDeleteResult:
            def __init__(self, deleted_count):
                self.deleted_count = deleted_count

        class FakeInvitesCollection:
            def __init__(self, invite):
                self.invite = dict(invite)
                self.deleted_query = None

            def find_one(self, query):
                if query.get("_id") == self.invite.get("_id"):
                    return dict(self.invite)
                return None

            def delete_one(self, query):
                self.deleted_query = dict(query)
                return FakeDeleteResult(1)

        fake_invites = FakeInvitesCollection(invite_document)
        with (
            patch.object(household_access_service, "_to_oid", return_value="invite-delete-1"),
            patch.object(household_access_service, "_invites", return_value=fake_invites),
            patch.object(
                household_access_service,
                "_find_project",
                return_value={"_id": "project-delete-1", "owner_user_id": "owner-1", "owner_email": "owner@example.com"},
            ),
            patch.object(household_access_service, "_resolve_actor_role", return_value="billing_owner"),
            patch.object(household_access_service, "create_audit_log") as audit_log_mock,
        ):
            deleted = household_access_service.delete_household_invite(
                invite_id="invite-delete-1",
                actor_user={"id": "owner-1", "email": "owner@example.com"},
            )

        self.assertTrue(deleted)
        self.assertEqual(fake_invites.deleted_query, {"_id": "invite-delete-1"})
        audit_log_mock.assert_called_once()

    def test_delete_household_invite_rejects_pending_records(self):
        invite_document = {
            "_id": "invite-delete-pending",
            "project_id": "project-delete-2",
            "status": "pending",
        }

        class FakeInvitesCollection:
            def __init__(self, invite):
                self.invite = dict(invite)

            def find_one(self, query):
                if query.get("_id") == self.invite.get("_id"):
                    return dict(self.invite)
                return None

            def delete_one(self, _query):
                raise AssertionError("delete_one should not be called for pending invites")

        fake_invites = FakeInvitesCollection(invite_document)
        with (
            patch.object(household_access_service, "_to_oid", return_value="invite-delete-pending"),
            patch.object(household_access_service, "_invites", return_value=fake_invites),
            patch.object(
                household_access_service,
                "_find_project",
                return_value={"_id": "project-delete-2", "owner_user_id": "owner-1", "owner_email": "owner@example.com"},
            ),
            patch.object(household_access_service, "_resolve_actor_role", return_value="billing_owner"),
        ):
            with self.assertRaises(ValueError) as error:
                household_access_service.delete_household_invite(
                    invite_id="invite-delete-pending",
                    actor_user={"id": "owner-1", "email": "owner@example.com"},
                )
        self.assertIn("revoked before deletion", str(error.exception))


if __name__ == "__main__":
    unittest.main()
