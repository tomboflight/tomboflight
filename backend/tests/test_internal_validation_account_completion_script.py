import importlib
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from bson import ObjectId

from scripts import complete_internal_validation_accounts as script


class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, n):
        return _FakeCursor(self._docs[:n])

    def __iter__(self):
        return iter(self._docs)


class _FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.writes = []

    def _matches(self, doc, query):
        if not query:
            return True
        if "$or" in query:
            return any(self._matches(doc, item) for item in query["$or"])
        for key, expected in query.items():
            if key == "$or":
                continue
            value = doc.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if value not in expected["$in"]:
                    return False
            else:
                if value != expected:
                    return False
        return True

    def find_one(self, query=None, sort=None):
        del sort
        query = query or {}
        for doc in self.docs:
            if self._matches(doc, query):
                return dict(doc)
        return None

    def find(self, query=None, *_args, **_kwargs):
        query = query or {}
        filtered = [dict(doc) for doc in self.docs if self._matches(doc, query)]
        return _FakeCursor(filtered)

    def count_documents(self, query):
        return len([doc for doc in self.docs if self._matches(doc, query)])

    def _write(self, name):
        self.writes.append(name)
        raise AssertionError(f"Write attempted in audit mode via {name}")

    def insert_one(self, *_args, **_kwargs):
        self._write("insert_one")

    def insert_many(self, *_args, **_kwargs):
        self._write("insert_many")

    def update_one(self, *_args, **_kwargs):
        self._write("update_one")

    def update_many(self, *_args, **_kwargs):
        self._write("update_many")

    def replace_one(self, *_args, **_kwargs):
        self._write("replace_one")

    def delete_one(self, *_args, **_kwargs):
        self._write("delete_one")

    def delete_many(self, *_args, **_kwargs):
        self._write("delete_many")

    def find_one_and_update(self, *_args, **_kwargs):
        self._write("find_one_and_update")

    def bulk_write(self, *_args, **_kwargs):
        self._write("bulk_write")


class _FakeDB(dict):
    def __init__(self):
        self.name = "tomboflight"
        specs = script.account_specs()
        users = []
        projects = []
        entitlements = []
        intakes = []
        orders = []
        families = []
        households = []
        project_members = []
        maintenance_sponsorships = []
        for spec in specs.values():
            users.append(
                {
                    "_id": ObjectId(spec.user_id),
                    "email": spec.email,
                    "full_name": spec.full_name,
                }
            )
            projects.append(
                {
                    "_id": ObjectId(spec.project_id),
                    "owner_user_id": spec.user_id,
                    "owner_email": spec.email,
                    "project_name": spec.expected_project_name,
                    "package_code": spec.expected_package_code,
                    "project_lane": spec.expected_lane,
                    "family_id": spec.family_id,
                    "household_id": spec.household_id,
                }
            )
            entitlements.append(
                {
                    "_id": ObjectId(),
                    "project_id": ObjectId(spec.project_id),
                    "user_id": ObjectId(spec.user_id),
                    "package_code": spec.expected_package_code,
                    "package_lane": spec.expected_lane,
                    "maintenance_plan": "none",
                    "maintenance_status": "not_started",
                }
            )
            intakes.append({"_id": ObjectId(spec.intake_submission_id), "project_id": ObjectId(spec.project_id), "email": spec.email})
            families.append({"_id": ObjectId(spec.family_id)})
            households.append({"_id": ObjectId(spec.household_id)})
            project_members.append(
                {
                    "_id": ObjectId(),
                    "project_id": ObjectId(spec.project_id),
                    "user_id": spec.user_id,
                    "email": spec.email,
                    "member_role": "billing_owner",
                    "status": "active",
                }
            )
            orders.append(
                {
                    "_id": ObjectId(),
                    "email": spec.email,
                    "project_id": ObjectId(spec.project_id),
                    "status": "paid",
                    "stripe_payment_link_id": spec.required_payment_link_id,
                    "promotion_code": "promo",
                    "package_code": spec.expected_package_code,
                }
            )
        finance_events = [
            {
                "_id": ObjectId(),
                "event_type": "package_upgrade",
                "project_id": ObjectId(specs["keith_goffigan"].project_id),
                "customer_email": specs["keith_goffigan"].email,
                "details": {"authorization_source": "stored_record"},
            }
        ]
        mint_records = [
            {
                "_id": ObjectId(script.EXPECTED_LARRY_CANONICAL_MINT["mint_record_id"]),
                "project_id": ObjectId(specs["larry_robinson"].project_id),
                "canonical": True,
                "token_id": script.EXPECTED_LARRY_CANONICAL_MINT["token_id"],
                "chain": script.EXPECTED_LARRY_CANONICAL_MINT["chain"],
                "contract_address": script.EXPECTED_LARRY_CANONICAL_MINT["contract_address"],
                "tx_hash": script.EXPECTED_LARRY_CANONICAL_MINT["tx_hash"],
                "wallet_address": script.EXPECTED_LARRY_CANONICAL_MINT["wallet_address"],
                "version_number": script.EXPECTED_LARRY_CANONICAL_MINT["version_number"],
            }
        ]

        super().__init__(
            {
                "users": _FakeCollection(users),
                "projects": _FakeCollection(projects),
                "project_entitlements": _FakeCollection(entitlements),
                "intake_submissions": _FakeCollection(intakes),
                "orders": _FakeCollection(orders),
                "finance_events": _FakeCollection(finance_events),
                "maintenance_sponsorships": _FakeCollection(maintenance_sponsorships),
                "mint_records": _FakeCollection(mint_records),
                "families": _FakeCollection(families),
                "households": _FakeCollection(households),
                "project_members": _FakeCollection(project_members),
                "uploaded_files": _FakeCollection([]),
                "vault_files": _FakeCollection([]),
                "issued_certificates": _FakeCollection([]),
            }
        )

    def __getitem__(self, item):
        return super().__getitem__(item)


class InternalValidationAccountCompletionScriptTests(unittest.TestCase):
    def test_apply_mode_requires_confirmation_phrase(self):
        with (
            patch.object(
                sys,
                "argv",
                [
                    "complete_internal_validation_accounts.py",
                    "--apply",
                    "--confirm-apply",
                    "WRONG",
                    "--environment",
                    "production",
                    "--database-name",
                    "tomboflight",
                    "--report-path",
                    "/tmp/report.json",
                ],
            ),
            patch.object(script, "connect_to_mongo") as connect_mock,
        ):
            result = script.main()
        self.assertEqual(result, 2)
        connect_mock.assert_not_called()

    def test_account_specs_exact_expected_values(self):
        specs = script.account_specs()
        self.assertEqual(specs["jennifer_wood"].user_id, "69c5c8db3bb71c27eee96ec6")
        self.assertEqual(specs["jennifer_wood"].project_id, "69c5d5023bb71c27eee96ed5")
        self.assertEqual(specs["jennifer_wood"].family_id, "69c5d5023bb71c27eee96ed3")
        self.assertEqual(specs["jennifer_wood"].household_id, "69c5d5023bb71c27eee96ed4")
        self.assertEqual(specs["jennifer_wood"].intake_submission_id, "69c5d3b83bb71c27eee96ed2")
        self.assertEqual(specs["jennifer_wood"].email, "queenjwood@gmail.com")
        self.assertEqual(specs["jennifer_wood"].expected_package_code, "digital_legacy_portrait")
        self.assertEqual(specs["jennifer_wood"].expected_lane, "portrait")

        self.assertEqual(specs["marquis_floyd"].user_id, "69c5c94d3bb71c27eee96ec7")
        self.assertEqual(specs["marquis_floyd"].project_id, "69c5db693bb71c27eee96edc")
        self.assertEqual(specs["marquis_floyd"].family_id, "69c5db693bb71c27eee96eda")
        self.assertEqual(specs["marquis_floyd"].household_id, "69c5db693bb71c27eee96edb")
        self.assertEqual(specs["marquis_floyd"].intake_submission_id, "69c5d95e3bb71c27eee96ed9")
        self.assertEqual(specs["marquis_floyd"].email, "mlfloyd00@gmail.com")
        self.assertEqual(specs["marquis_floyd"].expected_package_code, "digital_legacy_portrait")
        self.assertEqual(specs["marquis_floyd"].expected_lane, "portrait")

        self.assertEqual(specs["keith_goffigan"].user_id, "69c5c8493bb71c27eee96ec5")
        self.assertEqual(specs["keith_goffigan"].project_id, "69c5d6c43bb71c27eee96ed8")
        self.assertEqual(specs["keith_goffigan"].family_id, "69c5d6c43bb71c27eee96ed6")
        self.assertEqual(specs["keith_goffigan"].household_id, "69c5d6c43bb71c27eee96ed7")
        self.assertEqual(specs["keith_goffigan"].intake_submission_id, "69c5d1a83bb71c27eee96ed1")
        self.assertEqual(specs["keith_goffigan"].email, "chief757@outlook.com")
        self.assertEqual(specs["keith_goffigan"].expected_package_code, "household_foundation")
        self.assertEqual(specs["keith_goffigan"].expected_lane, "household")
        self.assertEqual(specs["keith_goffigan"].original_package_code, "digital_legacy_portrait")

        self.assertEqual(specs["larry_robinson"].user_id, "69be17d9c6ef5c9cb36af187")
        self.assertEqual(specs["larry_robinson"].project_id, "69c0402387082765345cff8c")
        self.assertEqual(specs["larry_robinson"].family_id, "69bf98b54c5cb5a4236446dd")
        self.assertEqual(specs["larry_robinson"].household_id, "69c0402387082765345cff8b")
        self.assertEqual(specs["larry_robinson"].intake_submission_id, "69bf55189e86117b345ec516")
        self.assertEqual(specs["larry_robinson"].email, "larrycr27@gmail.com")
        self.assertEqual(specs["larry_robinson"].expected_package_code, "legacy_plus")
        self.assertEqual(specs["larry_robinson"].expected_lane, "household")

    def test_audit_mode_main_performs_no_writes(self):
        fake_db = _FakeDB()
        with (
            patch.object(sys, "argv", ["complete_internal_validation_accounts.py", "--database-name", "tomboflight"]),
            patch.object(script, "connect_to_mongo", return_value=fake_db),
            patch.object(script, "close_mongo_connection"),
        ):
            exit_code = script.main()
        self.assertIn(exit_code, {0, 20})
        for collection in fake_db.values():
            self.assertEqual(collection.writes, [])

    def test_module_import_does_not_connect_database(self):
        module_name = "scripts.complete_internal_validation_accounts"
        prior = sys.modules.pop(module_name, None)
        try:
            with patch("app.database.connect_to_mongo") as connect_mock:
                loaded = importlib.import_module(module_name)
            self.assertIsInstance(loaded, ModuleType)
            connect_mock.assert_not_called()
        finally:
            if prior is not None:
                sys.modules[module_name] = prior
            else:
                sys.modules.pop(module_name, None)

    def test_intended_state_summary_lists_all_accounts(self):
        summary = script.build_intended_state_summary(script.account_specs())
        self.assertEqual(len(summary), 4)
        keys = {item["account_key"] for item in summary}
        self.assertEqual(keys, {"jennifer_wood", "marquis_floyd", "keith_goffigan", "larry_robinson"})


if __name__ == "__main__":
    unittest.main()
