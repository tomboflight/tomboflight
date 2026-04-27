import unittest
from copy import deepcopy
from unittest.mock import patch

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


class AdminAccessBootstrapTests(unittest.TestCase):
    def test_officer_role_mapping_normalizes_expected_roles(self):
        mapping = normalized_officer_role_mapping()
        self.assertEqual(
            mapping["l.robinson@tomboflight.com"],
            ["ceo_super_admin", "executive_tech_admin"],
        )
        self.assertNotIn("l.robinson@tomboflight", mapping)
        self.assertEqual(mapping["jenn.wood@tomboflight.com"], ["finance_admin"])
        self.assertEqual(mapping["marquis.l.floyd@tomboflight.com"], ["marketing_admin"])
        self.assertEqual(mapping["k.goffigan@tomboflight.com"], ["operations_admin"])

    def test_bootstrap_updates_existing_users_without_duplicate_role_assignments(self):
        users = [
            {"_id": "u-larry", "email": "l.robinson@tomboflight.com", "role": "admin"},
            {"_id": "u-jenn", "email": "jenn.wood@tomboflight.com", "role": "admin"},
            {"_id": "u-marquis", "email": "marquis.l.floyd@tomboflight.com", "role": "admin"},
            {"_id": "u-keith", "email": "k.goffigan@tomboflight.com", "role": "admin"},
        ]
        db = FakeDatabase({"users": deepcopy(users)})

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
        self.assertEqual(larry_roles, ["ceo_super_admin", "executive_tech_admin"])

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
        self.assertEqual(marquis_roles, ["marketing_admin"])
        self.assertEqual(keith_roles, ["operations_admin"])


if __name__ == "__main__":
    unittest.main()
