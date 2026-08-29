import asyncio
import unittest
from copy import deepcopy
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException

from app.dependencies import auth as auth_dependencies
from app.routes import admin_control_center as admin_control_routes


class TrackingCollection:
    def __init__(self, documents=None):
        self.documents = deepcopy(list(documents or []))
        self.find_queries = []
        self.write_calls = 0

    def find(self, query=None, projection=None, *args, **kwargs):
        del projection, args, kwargs
        query = query or {}
        self.find_queries.append(deepcopy(query))
        return [document for document in self.documents if self._matches(document, query)]

    def find_one(self, query=None, projection=None, *args, **kwargs):
        del projection, args, kwargs
        query = query or {}
        for document in self.documents:
            if self._matches(document, query):
                return document
        return None

    def count_documents(self, query=None):
        query = query or {}
        return len([document for document in self.documents if self._matches(document, query)])

    def insert_one(self, *_args, **_kwargs):
        self.write_calls += 1
        raise AssertionError("Unexpected write during access-context resolution.")

    def update_one(self, *_args, **_kwargs):
        self.write_calls += 1
        raise AssertionError("Unexpected write during access-context resolution.")

    def update_many(self, *_args, **_kwargs):
        self.write_calls += 1
        raise AssertionError("Unexpected write during access-context resolution.")

    @staticmethod
    def _matches(document, query):
        for key, expected in (query or {}).items():
            if key == "$or":
                if not any(TrackingCollection._matches(document, option) for option in expected):
                    return False
                continue
            actual = document.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if actual not in expected["$in"]:
                    return False
                continue
            if actual != expected:
                return False
        return True


class TrackingDatabase:
    def __init__(self, collections=None):
        self.collections = {
            name: TrackingCollection(documents)
            for name, documents in (collections or {}).items()
        }
        self.item_lookups = []

    def __getitem__(self, name):
        self.item_lookups.append(name)
        if name not in self.collections:
            self.collections[name] = TrackingCollection()
        return self.collections[name]


class PyMongoLikeDatabase(TrackingDatabase):
    def __init__(self, collections=None):
        super().__init__(collections=collections)
        self.attribute_lookups = []

    def __getattr__(self, name):
        self.attribute_lookups.append(name)
        return self[name]


class AdminAuthOverrideHotfixTests(unittest.TestCase):
    def test_collect_overrides_uses_getitem_for_pymongo_like_database(self):
        database = PyMongoLikeDatabase(
            {
                "user_permission_overrides": [
                    {"user_id": "user-1", "permission_code": "admin.audit.read", "status": "active"},
                ]
            }
        )

        with patch.object(auth_dependencies, "_db", return_value=database):
            permissions = auth_dependencies._collect_user_permission_overrides("USER-1")

        self.assertEqual(permissions, {"admin.audit.read"})
        self.assertIn("user_permission_overrides", database.item_lookups)
        self.assertNotIn("get", database.attribute_lookups)

    def test_collect_overrides_supports_objectid_identifier_and_does_not_mutate_docs(self):
        user_id = ObjectId()
        override_document = {
            "user_id": str(user_id),
            "permission_code": "admin.control.billing",
            "status": "enabled",
        }
        database = TrackingDatabase({"user_permission_overrides": [override_document]})
        before = deepcopy(database["user_permission_overrides"].documents)

        with patch.object(auth_dependencies, "_db", return_value=database):
            permissions = auth_dependencies._collect_user_permission_overrides(user_id)

        self.assertEqual(permissions, {"admin.control.billing"})
        self.assertEqual(database["user_permission_overrides"].documents, before)

    def test_resolve_access_context_without_override_keeps_base_role_permissions(self):
        user = {
            "_id": "u-finance",
            "email": "finance-admin@example.com",
            "role": "admin",
            "access_tier": "finance_admin",
            "department_role": "finance_admin",
        }
        database = TrackingDatabase(
            {
                "user_role_assignments": [],
                "role_permissions": [],
                "role_capabilities": [],
                "user_permission_overrides": [],
                "projects": [],
                "workflow_events": [],
                "mint_records": [{"mint_id": "larry-canonical-mint", "status": "locked"}],
            }
        )
        mint_before = deepcopy(database["mint_records"].documents)

        with (
            patch.object(auth_dependencies, "_load_user_by_id", return_value=user),
            patch.object(auth_dependencies, "_db", return_value=database),
            patch.object(auth_dependencies, "list_user_project_entitlements", return_value=[]),
            patch.object(auth_dependencies, "create_workflow_event") as workflow_event_mock,
        ):
            context = auth_dependencies.resolve_access_context("u-finance")

        permissions = set(context["permissions"])
        self.assertIn("admin.control.billing", permissions)
        self.assertNotIn("*", permissions)
        self.assertEqual(context["project_scope"], {"scope": "all", "project_count": 0})
        self.assertEqual(database["mint_records"].documents, mint_before)
        workflow_event_mock.assert_not_called()

        total_writes = sum(collection.write_calls for collection in database.collections.values())
        self.assertEqual(total_writes, 0)

    def test_resolve_access_context_applies_only_active_override_records(self):
        user = {
            "_id": "u-larry",
            "email": "ceo-admin@example.com",
            "role": "admin",
            "access_tier": "ceo_master_admin",
            "department_role": "executive_tech_admin",
        }
        override_docs = [
            {"user_id": "u-larry", "permission_code": "admin.control.mint", "status": "active"},
            {"user_id": "u-larry", "permission_code": "admin.orders.read", "status": "disabled"},
            {"user_id": "u-other", "permission_code": "admin.audit.read", "status": "active"},
        ]
        database = TrackingDatabase(
            {
                "user_role_assignments": [],
                "role_permissions": [],
                "role_capabilities": [],
                "user_permission_overrides": override_docs,
                "projects": [],
                "workflow_events": [],
            }
        )
        overrides_before = deepcopy(database["user_permission_overrides"].documents)

        with (
            patch.object(auth_dependencies, "_load_user_by_id", return_value=user),
            patch.object(auth_dependencies, "_db", return_value=database),
            patch.object(auth_dependencies, "list_user_project_entitlements", return_value=[]),
        ):
            context = auth_dependencies.resolve_access_context("u-larry")

        permissions = set(context["permissions"])
        self.assertIn("*", permissions)
        self.assertIn("admin.control.mint", permissions)
        override_queries = database["user_permission_overrides"].find_queries
        self.assertTrue(override_queries)
        self.assertEqual(
            override_queries[-1],
            {
                "user_id": "u-larry",
                "status": {"$in": ["active", "enabled", ""]},
            },
        )
        self.assertEqual(database["user_permission_overrides"].documents, overrides_before)

    def test_access_profile_and_overview_cases_succeed_for_ceo_master_admin(self):
        current_user = {
            "role": "admin",
            "access_tier": "ceo_master_admin",
            "_access_context": {
                "role_codes": ["ceo_master_admin", "executive_tech_admin"],
                "permissions": ["*"],
            },
        }

        profile = admin_control_routes.get_admin_control_access_profile(current_user=current_user)
        self.assertTrue(profile["is_wildcard"])
        self.assertIn("overview", profile["allowed_queues"])
        self.assertIn("customer_cases", profile["allowed_queues"])
        self.assertIn("users", profile["allowed_queues"])

        with patch.object(
            admin_control_routes,
            "list_customer_cases",
            return_value={
                "items": [{"id": "case-1", "customer_email": "larry@example.com"}],
                "metrics": {"customers": 1, "projects": 2, "orders": 3},
            },
        ):
            payload = asyncio.run(
                admin_control_routes.get_customer_cases(
                    search="larry",
                    queue="overview",
                    limit=50,
                    current_user=current_user,
                )
            )

        self.assertEqual(payload["metrics"], {"customers": 1, "projects": 2, "orders": 3})
        self.assertTrue(payload["items"])

    def test_isolation_customer_denied_and_officer_scopes_limited(self):
        customer_user = {
            "role": "user",
            "_access_context": {"role_codes": ["user"], "permissions": []},
        }
        with self.assertRaises(HTTPException) as denied_error:
            asyncio.run(
                admin_control_routes.get_customer_cases(
                    search="",
                    queue="overview",
                    limit=10,
                    current_user=customer_user,
                )
            )
        self.assertEqual(denied_error.exception.status_code, 403)

        finance_user = {
            "role": "admin",
            "access_tier": "finance_admin",
            "_access_context": {
                "role_codes": ["finance_admin"],
                "permissions": ["admin.control.billing", "admin.orders.read", "admin.audit.read"],
            },
        }
        operations_user = {
            "role": "admin",
            "access_tier": "operations_admin",
            "_access_context": {
                "role_codes": ["operations_admin"],
                "permissions": ["admin.control.view", "admin.intake.review"],
            },
        }
        marketing_user = {
            "role": "admin",
            "access_tier": "marketing_admin",
            "_access_context": {
                "role_codes": ["marketing_admin"],
                "permissions": ["admin.analytics.read"],
            },
        }

        finance_profile = admin_control_routes.get_admin_control_access_profile(current_user=finance_user)
        operations_profile = admin_control_routes.get_admin_control_access_profile(current_user=operations_user)
        marketing_profile = admin_control_routes.get_admin_control_access_profile(current_user=marketing_user)

        self.assertIn("money_now", finance_profile["allowed_queues"])
        self.assertNotIn("users", finance_profile["allowed_queues"])
        self.assertIn("ops_reports", operations_profile["allowed_queues"])
        self.assertNotIn("money_now", operations_profile["allowed_queues"])
        self.assertIn("traffic_awareness", marketing_profile["allowed_queues"])
        self.assertNotIn("customer_cases", marketing_profile["allowed_queues"])


if __name__ == "__main__":
    unittest.main()
