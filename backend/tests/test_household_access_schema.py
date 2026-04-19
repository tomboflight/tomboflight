import unittest

from app.schemas.household_access import build_invite_response


class HouseholdAccessSchemaTests(unittest.TestCase):
    def test_build_invite_response_coerces_invalid_usage_fields(self):
        payload = build_invite_response(
            {
                "_id": "invite-legacy",
                "project_id": "project-1",
                "email": "legacy@example.com",
                "status": "expired",
                "member_role": "viewer",
                "max_uses": "legacy",
                "use_count": "not_a_number",
            }
        )
        self.assertEqual(payload["max_uses"], 1)
        self.assertEqual(payload["use_count"], 0)

    def test_build_invite_response_clamps_negative_usage_fields(self):
        payload = build_invite_response(
            {
                "_id": "invite-legacy-negative",
                "project_id": "project-2",
                "email": "legacy2@example.com",
                "status": "expired",
                "member_role": "viewer",
                "max_uses": -3,
                "use_count": -7,
            }
        )
        self.assertEqual(payload["max_uses"], 1)
        self.assertEqual(payload["use_count"], 0)

    def test_build_invite_response_includes_email_delivery_fields(self):
        payload = build_invite_response(
            {
                "_id": "invite-email-delivery",
                "project_id": "project-3",
                "email": "delivery@example.com",
                "status": "pending",
                "member_role": "viewer",
                "email_delivery_status": "failed",
                "email_delivery_error": "postmark_token_missing",
            }
        )
        self.assertEqual(payload["email_delivery_status"], "failed")
        self.assertEqual(payload["email_delivery_error"], "postmark_token_missing")


if __name__ == "__main__":
    unittest.main()
