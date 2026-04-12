import unittest

from app.dependencies import auth as auth_dependencies
from app.services.auth_service import build_user_response


class AccountSeparationTests(unittest.TestCase):
    def test_admin_role_does_not_inherit_customer_package_capabilities(self):
        admin_user = {
            "email": "l.robinson@tomboflight.com",
            "role": "admin",
            "access_tier": "super_admin",
            "department_role": "executive_technology",
        }

        self.assertEqual(auth_dependencies.get_user_package_capabilities(admin_user), set())
        self.assertFalse(
            auth_dependencies.has_package_capability(admin_user, "can_use_viewer")
        )
        self.assertTrue(
            auth_dependencies.has_package_capability(
                admin_user,
                "can_use_viewer",
                allow_internal_admin=True,
            )
        )

    def test_user_response_exposes_account_metadata(self):
        response = build_user_response(
            {
                "_id": "user-1",
                "email": "jenn.wood@tomboflight.com",
                "full_name": "Jennifer Wood",
                "role": "admin",
                "account_type": "business_admin",
                "business_title": "CFO",
                "access_tier": "finance_admin",
                "department_role": "finance",
                "status": "active",
                "created_at": "2026-03-22T17:15:53+00:00",
            }
        )

        self.assertEqual(response["account_type"], "business_admin")
        self.assertEqual(response["business_title"], "CFO")


if __name__ == "__main__":
    unittest.main()
