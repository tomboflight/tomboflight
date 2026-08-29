import unittest
from copy import deepcopy
import json
from unittest.mock import patch

from app.core import admin_permission_registry
from app.core.admin_permission_registry import normalized_officer_role_mapping
from app.services import admin_access_bootstrap_service


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = list(documents or [])
        self._counter = len(self.documents)

    def find_one(self, query):
        for document in self.documents:
            if self._matches(document, query):
                return document
        return None

    def update_one(self, query, update, upsert=False):
        existing = self.find_one(query)
        if existing is not None:
            for key, value in (update.get("$set") or {}).items():
                existing[key] = value
            return type(
                "Result",
                (),
                {
                    "matched_count": 1,
                    "modified_count": 1,
                    "upserted_id": None,
                },
            )()

        if upsert:
            self._counter += 1
            payload = dict(query)
            for key, value in (update.get("$setOnInsert") or {}).items():
                payload[key] = value
            for key, value in (update.get("$set") or {}).items():
                payload[key] = value
            payload.setdefault("_id", f"doc-{self._counter}")
            self.documents.append(payload)
            return type(
                "Result",
                (),
                {
                    "matched_count": 0,
                    "modified_count": 0,
                    "upserted_id": payload["_id"],
                },
            )()

        return type(
            "Result",
            (),
            {
                "matched_count": 0,
                "modified_count": 0,
                "upserted_id": None,
            },
        )()

    def update_many(self, query, update):
        modified = 0
        for document in self.documents:
            if not self._matches(document, query):
                continue
            for key, value in (update.get("$set") or {}).items():
                document[key] = value
            modified += 1
        return type("Result", (), {"modified_count": modified})()

    @staticmethod
    def _matches(document, query):
        for key, expected in (query or {}).items():
            if isinstance(expected, dict) and "$in" in expected:
                if document.get(key) not in set(expected["$in"]):
                    return False
                continue
            if isinstance(expected, dict) and "$nin" in expected:
                if document.get(key) in set(expected["$nin"]):
                    return False
                continue
            if document.get(key) != expected:
                return False
        return True


class FakeDatabase:
    def __init__(self, collections=None):
        self.collections = {
            name: FakeCollection(documents) for name, documents in (collections or {}).items()
        }

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        return self.collections[name]


class AdminIdentityRegistryConfigurationTests(unittest.TestCase):
    def test_missing_registry_never_matches_an_empty_identity(self):
        with patch.object(admin_permission_registry, "CEO_MASTER_ADMIN_EMAIL", ""):
            self.assertFalse(admin_permission_registry.is_canonical_ceo_email(""))
            self.assertFalse(admin_permission_registry.is_canonical_ceo_email(None))

    def test_registry_requires_exactly_one_ceo_identity(self):
        payload = {
            "active_officers": [
                {
                    "email": "first-ceo@example.com",
                    "role_codes": ["ceo_master_admin"],
                },
                {
                    "email": "second-ceo@example.com",
                    "role_codes": ["ceo_master_admin"],
                },
            ],
            "retired_officers": [],
        }
        _, _, _, _, errors, configured = (
            admin_permission_registry._load_admin_identity_registry(
                json.dumps(payload)
            )
        )

        self.assertTrue(configured)
        self.assertTrue(any("Exactly one" in error for error in errors))

    def test_registry_rejects_unscoped_privileged_roles(self):
        payload = {
            "active_officers": [
                {
                    "email": "ceo-admin@example.com",
                    "role_codes": ["ceo_master_admin"],
                },
                {
                    "email": "legacy-admin@example.com",
                    "role_codes": ["super_admin"],
                },
            ],
            "retired_officers": [],
        }
        _, mapping, _, _, errors, _ = (
            admin_permission_registry._load_admin_identity_registry(
                json.dumps(payload)
            )
        )

        self.assertNotIn("legacy-admin@example.com", mapping)
        self.assertTrue(any("unsupported role" in error for error in errors))

    def test_deployed_runtime_rejects_missing_or_invalid_registry(self):
        with (
            patch.object(
                admin_permission_registry,
                "ADMIN_IDENTITY_REGISTRY_CONFIGURED",
                False,
            ),
            patch.object(
                admin_permission_registry,
                "ADMIN_IDENTITY_REGISTRY_ERRORS",
                (),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "outside source control"):
                admin_permission_registry.validate_admin_identity_registry_configuration(
                    require_config=True
                )

        with (
            patch.object(
                admin_permission_registry,
                "ADMIN_IDENTITY_REGISTRY_CONFIGURED",
                True,
            ),
            patch.object(
                admin_permission_registry,
                "ADMIN_IDENTITY_REGISTRY_ERRORS",
                ("invalid registry",),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "invalid registry"):
                admin_permission_registry.validate_admin_identity_registry_configuration(
                    require_config=True
                )


class AdminAccessBootstrapTests(unittest.TestCase):
    def test_officer_role_mapping_normalizes_expected_roles(self):
        mapping = normalized_officer_role_mapping()
        self.assertEqual(
            mapping["ceo-admin@example.com"],
            ["ceo_master_admin", "executive_tech_admin"],
        )
        self.assertNotIn("ceo-admin@example", mapping)
        self.assertEqual(mapping["finance-admin@example.com"], ["finance_admin"])
        self.assertNotIn("retired-officer@example.com", mapping)
        self.assertEqual(mapping["operations-admin@example.com"], ["operations_admin"])

    def test_bootstrap_updates_existing_users_without_duplicate_role_assignments(self):
        users = [
            {"_id": "u-larry", "email": "ceo-admin@example.com", "role": "admin"},
            {"_id": "u-jenn", "email": "finance-admin@example.com", "role": "admin"},
            {"_id": "u-marquis", "email": "retired-officer@example.com", "role": "admin"},
            {"_id": "u-keith", "email": "operations-admin@example.com", "role": "admin"},
        ]
        db = FakeDatabase(
            {
                "users": deepcopy(users),
                "user_role_assignments": [
                    {"_id": "marquis-role", "user_id": "u-marquis", "role_code": "marketing_admin", "status": "active"},
                ],
                "user_permission_overrides": [
                    {"_id": "marquis-override", "user_id": "u-marquis", "permission_code": "admin.analytics.read", "status": "active"},
                ],
            }
        )

        with patch.object(admin_access_bootstrap_service, "get_database", return_value=db):
            first_result = admin_access_bootstrap_service.bootstrap_admin_access_controls()
            second_result = admin_access_bootstrap_service.bootstrap_admin_access_controls()

        self.assertEqual(len(db["users"].documents), 4)
        self.assertGreater(first_result["officers"]["assignments_created"], 0)
        self.assertEqual(second_result["officers"]["assignments_created"], 0)

        user_role_assignments = db["user_role_assignments"].documents
        assignment_keys = {(doc["user_id"], doc["role_code"]) for doc in user_role_assignments}
        self.assertEqual(len(user_role_assignments), len(assignment_keys))

        larry_roles = sorted(
            doc["role_code"]
            for doc in user_role_assignments
            if doc["user_id"] == "u-larry" and doc.get("status") == "active"
        )
        self.assertEqual(larry_roles, ["ceo_master_admin", "executive_tech_admin"])
        self.assertNotIn(
            ("u-jenn", "ceo_master_admin"),
            assignment_keys,
        )

        jenn_roles = [
            doc["role_code"]
            for doc in user_role_assignments
            if doc["user_id"] == "u-jenn" and doc.get("status") == "active"
        ]
        marquis_roles = [
            doc["role_code"]
            for doc in user_role_assignments
            if doc["user_id"] == "u-marquis" and doc.get("status") == "active"
        ]
        keith_roles = [
            doc["role_code"]
            for doc in user_role_assignments
            if doc["user_id"] == "u-keith" and doc.get("status") == "active"
        ]
        self.assertEqual(jenn_roles, ["finance_admin"])
        self.assertEqual(marquis_roles, [])
        self.assertEqual(keith_roles, ["operations_admin"])

        marquis_user = db["users"].find_one({"_id": "u-marquis"})
        self.assertEqual(marquis_user["status"], "archived")
        self.assertEqual(marquis_user["role"], "user")
        self.assertEqual(marquis_user["account_type"], "former_business_admin")
        self.assertFalse(marquis_user["login_enabled"])
        self.assertEqual(marquis_user["session_token_version"], 1)
        self.assertEqual(
            db["user_permission_overrides"].find_one({"_id": "marquis-override"})["status"],
            "inactive",
        )
        self.assertGreaterEqual(first_result["retired_officers"]["assignments_disabled"], 1)

    def test_bootstrap_preserves_ceo_assigned_job_scope_for_active_officer(self):
        db = FakeDatabase(
            {
                "users": [
                    {"_id": "u-larry", "email": "ceo-admin@example.com", "role": "admin"},
                    {
                        "_id": "u-jenn",
                        "email": "finance-admin@example.com",
                        "role": "admin",
                        "access_tier": "finance_admin",
                        "department_role": "finance_admin",
                        "managed_role_code": "marketing_admin",
                    },
                    {"_id": "u-keith", "email": "operations-admin@example.com", "role": "admin"},
                ],
                "user_role_assignments": [
                    {"_id": "jenn-finance", "user_id": "u-jenn", "role_code": "finance_admin", "status": "active"},
                    {"_id": "jenn-marketing", "user_id": "u-jenn", "role_code": "marketing_admin", "status": "active"},
                ],
            }
        )

        with patch.object(admin_access_bootstrap_service, "get_database", return_value=db):
            admin_access_bootstrap_service.bootstrap_admin_access_controls()

        jenn = db["users"].find_one({"_id": "u-jenn"}) or {}
        self.assertEqual(jenn.get("access_tier"), "marketing_admin")
        self.assertEqual(jenn.get("department_role"), "marketing_admin")
        active_roles = sorted(
            item.get("role_code")
            for item in db["user_role_assignments"].documents
            if item.get("user_id") == "u-jenn" and item.get("status") == "active"
        )
        self.assertEqual(active_roles, ["marketing_admin"])


if __name__ == "__main__":
    unittest.main()
