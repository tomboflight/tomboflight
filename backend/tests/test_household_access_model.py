import unittest

from app.core.role_catalog import normalize_project_member_role
from app.schemas.link_key import build_link_key_response
from app.services.privacy_access_service import (
    can_access_cinematic_asset,
    can_access_privacy_scope,
    normalize_privacy_scope,
)


class HouseholdAccessModelTests(unittest.TestCase):
    def test_customer_membership_role_aliases_are_normalized(self):
        self.assertEqual(normalize_project_member_role("owner"), "billing_owner")
        self.assertEqual(normalize_project_member_role("spouse"), "co_owner")
        self.assertEqual(normalize_project_member_role("manager"), "family_manager")
        self.assertEqual(normalize_project_member_role("editor"), "contributor")

    def test_privacy_scope_authorization_uses_role_relationship_and_link_status(self):
        self.assertTrue(
            can_access_privacy_scope(
                privacy_scope="private_to_owner_and_co_owner",
                member_role="co_owner",
                relationship_scope="household_member",
                link_status="active",
                is_owner=False,
            )
        )
        self.assertFalse(
            can_access_privacy_scope(
                privacy_scope="private_to_owner",
                member_role="co_owner",
                relationship_scope="household_member",
                link_status="active",
                is_owner=False,
            )
        )
        self.assertTrue(
            can_access_privacy_scope(
                privacy_scope="linked_family_shared",
                member_role="linked_relative",
                relationship_scope="linked_relative",
                link_status="approved",
                is_owner=False,
            )
        )
        self.assertFalse(
            can_access_privacy_scope(
                privacy_scope="linked_family_shared",
                member_role="linked_relative",
                relationship_scope="linked_relative",
                link_status="pending",
                is_owner=False,
            )
        )

    def test_cinematic_asset_requires_approval_and_scope_access(self):
        approved_asset = {
            "approved_for_cinematic": True,
            "verification_status": "approved",
            "consent_status": "approved",
            "privacy_scope": normalize_privacy_scope("household_private"),
        }
        denied_asset = dict(approved_asset, approved_for_cinematic=False)
        self.assertTrue(
            can_access_cinematic_asset(
                asset=approved_asset,
                member_role="co_owner",
                relationship_scope="household_member",
                link_status="active",
                is_owner=False,
            )
        )
        self.assertFalse(
            can_access_cinematic_asset(
                asset=denied_asset,
                member_role="co_owner",
                relationship_scope="household_member",
                link_status="active",
                is_owner=False,
            )
        )

    def test_link_key_response_includes_typed_key_metadata(self):
        response = build_link_key_response(
            {
                "_id": "key-1",
                "project_id": "project-1",
                "key_type": "household_invite_key",
                "key_value": "hhinv_abc123",
                "status": "active",
                "issuer_user_id": "owner-1",
                "target_email": "invitee@example.com",
                "allowed_role": "viewer",
                "max_uses": 3,
                "use_count": 1,
                "created_at": "2026-04-15T00:00:00Z",
            }
        )
        self.assertEqual(response.key_type, "household_invite_key")
        self.assertEqual(response.max_uses, 3)
        self.assertEqual(response.use_count, 1)
        self.assertEqual(response.allowed_role, "viewer")


if __name__ == "__main__":
    unittest.main()
