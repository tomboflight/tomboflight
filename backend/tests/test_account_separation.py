import unittest
from typing import Any, cast
from unittest.mock import patch

from fastapi import HTTPException

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

    def test_require_permission_reuses_cached_access_context_for_same_project(self):
        dependency = auth_dependencies.require_permission("admin.access")
        current_user = {
            "id": "user-1",
            "_access_context": {
                "project_id": "project-1",
                "permissions": ["admin.access"],
            },
        }

        with (
            patch.object(
                auth_dependencies,
                "_extract_project_id_from_request",
                return_value="project-1",
            ),
            patch.object(auth_dependencies, "resolve_access_context") as resolve_mock,
        ):
            resolved_user = dependency(request=cast(Any, object()), current_user=current_user)

        self.assertIs(resolved_user, current_user)
        resolve_mock.assert_not_called()

    def test_require_permission_refreshes_context_for_different_project(self):
        dependency = auth_dependencies.require_permission("admin.access")
        current_user = {
            "id": "user-1",
            "_access_context": {
                "project_id": "project-1",
                "permissions": ["admin.access"],
            },
        }

        with (
            patch.object(
                auth_dependencies,
                "_extract_project_id_from_request",
                return_value="project-2",
            ),
            patch.object(
                auth_dependencies,
                "resolve_access_context",
                return_value={
                    "project_id": "project-2",
                    "permissions": ["admin.access"],
                },
            ) as resolve_mock,
        ):
            resolved_user = dependency(request=cast(Any, object()), current_user=current_user)

        self.assertIs(resolved_user, current_user)
        resolve_mock.assert_called_once_with("user-1", project_id="project-2")
        self.assertEqual(current_user["_access_context"]["project_id"], "project-2")

    def test_require_super_admin_rejects_non_super_admin_role(self):
        current_user = {
            "id": "user-1",
            "role": "admin",
            "_access_context": {
                "project_id": None,
                "role_codes": ["admin"],
                "permissions": ["*"],
            },
        }
        with patch.object(auth_dependencies, "_extract_project_id_from_request", return_value=""):
            with self.assertRaises(HTTPException) as error:
                auth_dependencies.require_super_admin(request=cast(Any, object()), current_user=current_user)
        self.assertEqual(error.exception.status_code, 403)

    def test_require_super_admin_allows_super_admin_role(self):
        current_user = {
            "id": "user-1",
            "role": "super_admin",
            "_access_context": {
                "project_id": None,
                "role_codes": ["super_admin"],
                "permissions": ["*"],
            },
        }
        with patch.object(auth_dependencies, "_extract_project_id_from_request", return_value=""):
            resolved = auth_dependencies.require_super_admin(request=cast(Any, object()), current_user=current_user)
        self.assertIs(resolved, current_user)

    def test_admin_base_role_does_not_grant_full_admin_permissions(self):
        with (
            patch.object(
                auth_dependencies,
                "_load_user_by_id",
                return_value={
                    "_id": "user-1",
                    "email": "jenn.wood@tomboflight.com",
                    "role": "admin",
                    "access_tier": "finance_admin",
                    "department_role": "finance",
                },
            ),
            patch.object(
                auth_dependencies,
                "_db",
                return_value={
                    "user_role_assignments": type("Collection", (), {"find": lambda self, *_a, **_k: []})(),
                    "role_permissions": type("Collection", (), {"find": lambda self, *_a, **_k: []})(),
                    "role_capabilities": type("Collection", (), {"find": lambda self, *_a, **_k: []})(),
                    "projects": type("Collection", (), {"count_documents": lambda self, *_a, **_k: 0})(),
                    "workflow_events": type("Collection", (), {"find_one": lambda self, *_a, **_k: None})(),
                },
            ),
            patch.object(auth_dependencies, "list_user_project_entitlements", return_value=[]),
        ):
            context = auth_dependencies.resolve_access_context("user-1")
        permissions = set(context.get("permissions") or [])
        self.assertIn("admin.control.billing", permissions)
        self.assertNotIn("admin.users.write", permissions)
        self.assertNotIn("admin.intake.write", permissions)


if __name__ == "__main__":
    unittest.main()
