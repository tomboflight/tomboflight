import unittest
from unittest.mock import patch

from app.services import project_membership_service
from app.services import project_entitlement_service


class InternalAccountServiceSafetyTests(unittest.TestCase):
    def test_ensure_project_owner_membership_delegates_with_billing_owner(self):
        project = {
            "_id": "69c5d6c43bb71c27eee96ed8",
            "owner_user_id": "69c5c8493bb71c27eee96ec5",
            "owner_email": "chief757@outlook.com",
        }
        with patch.object(
            project_membership_service,
            "ensure_project_member",
            return_value={"ok": True},
        ) as ensure_mock:
            result = project_membership_service.ensure_project_owner_membership(project)
        self.assertEqual(result, {"ok": True})
        ensure_mock.assert_called_once()
        kwargs = ensure_mock.call_args.kwargs
        self.assertEqual(kwargs["project_id"], "69c5d6c43bb71c27eee96ed8")
        self.assertEqual(kwargs["user_id"], "69c5c8493bb71c27eee96ec5")
        self.assertEqual(kwargs["email"], "chief757@outlook.com")
        self.assertEqual(kwargs["member_role"], "billing_owner")
        self.assertEqual(kwargs["status"], "active")

    def test_project_entitlement_id_candidates_include_string_and_objectid_forms(self):
        candidates = project_entitlement_service._project_id_candidates("69c5d6c43bb71c27eee96ed8")
        self.assertIn("69c5d6c43bb71c27eee96ed8", candidates)
        self.assertTrue(any(type(item).__name__ == "ObjectId" for item in candidates))

    def test_user_id_candidates_include_string_and_objectid(self):
        candidates = project_entitlement_service._user_id_candidates("69c5c8493bb71c27eee96ec5")
        self.assertIn("69c5c8493bb71c27eee96ec5", candidates)
        self.assertTrue(any(type(item).__name__ == "ObjectId" for item in candidates))


if __name__ == "__main__":
    unittest.main()
