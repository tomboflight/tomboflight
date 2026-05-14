from importlib import import_module
from pathlib import Path
import ast
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase5m_role_category_taxonomy.md"
VALIDATOR_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_validator.py"
PREVIEW_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_admin_preview.py"


class TestContinuityKernelPhase5MRoleCategoryTaxonomy(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_exists = DOC_PATH.exists()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if cls.doc_exists else ""
        cls.doc_lower = cls.doc_text.lower()

        cls.validator = import_module("backend.app.core.continuity_kernel_validator")
        cls.preview = import_module("backend.app.core.continuity_kernel_admin_preview")
        cls.validator_source = VALIDATOR_PATH.read_text(encoding="utf-8")
        cls.preview_source = PREVIEW_PATH.read_text(encoding="utf-8")
        cls.validator_lower = cls.validator_source.lower()
        cls.preview_lower = cls.preview_source.lower()

    def _authorization(self, role: str, category: str) -> dict:
        return {
            "actor_user_id": "actor-1",
            "actor_role": role,
            "requested_action": "approve_apply",
            "repair_category": category,
            "target_type": "workspace",
            "target_id": "ws-1",
            "decision": "approved",
            "reason_codes": ["policy_ok"],
            "policy_source": "phase5m-tests",
            "evaluated_at": "2099-01-01T00:00:00Z",
        }

    def test_01_phase5m_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_includes_all_canonical_officer_roles(self) -> None:
        for value in [
            "SUPERADMIN",
            "EXECUTIVE_TECH_ADMIN",
            "operations_admin",
            "finance_admin",
            "marketing_admin",
            "CMO",
        ]:
            self.assertIn(value, self.doc_text)

    def test_03_doc_includes_all_canonical_repair_categories(self) -> None:
        for value in [
            "missing_entitlement_repair",
            "package_lane_normalization",
            "workspace_membership_repair",
            "upload_readiness_repair",
            "viewer_readiness_repair",
            "certificate_issuance_consistency_repair",
            "mint_readiness_repair",
            "admin_repair_safety",
            "billing_order_payment_repair",
            "audit_record_correction_metadata",
        ]:
            self.assertIn(value, self.doc_text)

    def test_04_doc_includes_all_category_groups(self) -> None:
        for value in [
            "technical_categories",
            "operations_categories",
            "finance_categories",
            "marketing_categories",
            "superadmin_only_categories",
            "read_only_preview_categories",
        ]:
            self.assertIn(value, self.doc_text)

    def test_05_doc_says_no_substring_matching_for_authorization(self) -> None:
        self.assertIn("no substring matching for authorization", self.doc_lower)

    def test_06_doc_says_no_keyword_guessing_for_role_category_approval(self) -> None:
        self.assertIn("no keyword guessing for role/category approval", self.doc_lower)

    def test_07_doc_says_unknown_roles_fail_closed(self) -> None:
        self.assertIn("unknown roles fail closed", self.doc_lower)

    def test_08_doc_says_unknown_categories_fail_closed(self) -> None:
        self.assertIn("unknown categories fail closed", self.doc_lower)

    def test_09_validator_unknown_role_fails_closed(self) -> None:
        result = self.validator.validate_authorization_decision(
            self._authorization("unknown_role", "workspace_membership_repair")
        )
        self.assertFalse(result["passed"])

    def test_10_validator_unknown_category_fails_closed(self) -> None:
        result = self.validator.validate_authorization_decision(self._authorization("SUPERADMIN", "unknown_category"))
        self.assertFalse(result["passed"])

    def test_11_validator_marketing_admin_approval_fails_closed(self) -> None:
        result = self.validator.validate_authorization_decision(
            self._authorization("marketing_admin", "workspace_membership_repair")
        )
        self.assertFalse(result["passed"])

    def test_12_validator_cmo_approval_fails_closed(self) -> None:
        result = self.validator.validate_authorization_decision(self._authorization("CMO", "workspace_membership_repair"))
        self.assertFalse(result["passed"])

    def test_13_validator_superadmin_can_approve_all_canonical_categories(self) -> None:
        for category in self.validator.CANONICAL_REPAIR_CATEGORIES:
            result = self.validator.validate_authorization_decision(self._authorization("SUPERADMIN", category))
            self.assertTrue(result["passed"], msg=f"SUPERADMIN should approve category: {category}")

    def test_14_validator_operations_admin_can_approve_operations_categories_only(self) -> None:
        for category in self.validator.OPERATIONS_CATEGORIES:
            result = self.validator.validate_authorization_decision(self._authorization("operations_admin", category))
            self.assertTrue(result["passed"], msg=f"operations_admin should approve operations category: {category}")

        disallowed = set(self.validator.CANONICAL_REPAIR_CATEGORIES) - set(self.validator.OPERATIONS_CATEGORIES)
        for category in disallowed:
            result = self.validator.validate_authorization_decision(self._authorization("operations_admin", category))
            self.assertFalse(result["passed"], msg=f"operations_admin must not approve category: {category}")

    def test_15_validator_finance_admin_can_approve_finance_categories_only(self) -> None:
        for category in self.validator.FINANCE_CATEGORIES:
            result = self.validator.validate_authorization_decision(self._authorization("finance_admin", category))
            self.assertTrue(result["passed"], msg=f"finance_admin should approve finance category: {category}")

        disallowed = set(self.validator.CANONICAL_REPAIR_CATEGORIES) - set(self.validator.FINANCE_CATEGORIES)
        for category in disallowed:
            result = self.validator.validate_authorization_decision(self._authorization("finance_admin", category))
            self.assertFalse(result["passed"], msg=f"finance_admin must not approve category: {category}")

    def test_16_validator_executive_tech_admin_cannot_approve_finance_without_structured_override(self) -> None:
        result = self.validator.validate_authorization_decision(
            self._authorization("EXECUTIVE_TECH_ADMIN", "billing_order_payment_repair")
        )
        self.assertFalse(result["passed"])
        self.assertIn("STRUCTURED_OVERRIDE_REQUIRED", result["reason_codes"])

    def test_17_admin_preview_unknown_role_returns_no_actions(self) -> None:
        actions = self.preview.allowed_preview_actions_for_role("unknown_role", "workspace_membership_repair")
        self.assertEqual(actions, [])

    def test_18_admin_preview_unknown_category_returns_no_actions(self) -> None:
        actions = self.preview.allowed_preview_actions_for_role("SUPERADMIN", "unknown_category")
        self.assertEqual(actions, [])

    def test_19_admin_preview_marketing_admin_returns_no_actions(self) -> None:
        actions = self.preview.allowed_preview_actions_for_role("marketing_admin", "workspace_membership_repair")
        self.assertEqual(actions, [])

    def test_20_admin_preview_cmo_returns_no_actions(self) -> None:
        actions = self.preview.allowed_preview_actions_for_role("CMO", "workspace_membership_repair")
        self.assertEqual(actions, [])

    def test_21_admin_preview_superadmin_receives_read_only_actions_only(self) -> None:
        actions = self.preview.allowed_preview_actions_for_role("SUPERADMIN", "workspace_membership_repair")
        self.assertEqual(set(actions), set(self.preview.ALLOWED_READ_ONLY_ACTIONS))
        self.assertTrue(set(actions).isdisjoint(set(self.preview.PROHIBITED_ACTIONS)))

    def test_22_admin_preview_never_returns_prohibited_actions_for_any_role_category(self) -> None:
        roles = list(self.preview.CANONICAL_OFFICER_ROLES) + ["unknown_role"]
        categories = list(self.preview.CANONICAL_REPAIR_CATEGORIES) + ["unknown_category"]
        prohibited = set(self.preview.PROHIBITED_ACTIONS)
        for role in roles:
            for category in categories:
                actions = self.preview.allowed_preview_actions_for_role(role, category)
                self.assertTrue(set(actions).isdisjoint(prohibited), msg=f"Prohibited action found for {role}/{category}")

    def test_23_admin_preview_uses_explicit_category_constants_groups_not_keyword_matching(self) -> None:
        self.assertIn("TECHNICAL_CATEGORIES", self.preview_source)
        self.assertIn("OPERATIONS_CATEGORIES", self.preview_source)
        self.assertIn("FINANCE_CATEGORIES", self.preview_source)
        self.assertIn("ROLE_TO_PREVIEW_CATEGORIES", self.preview_source)
        self.assertNotIn("def _is_technical_category", self.preview_source)
        self.assertNotIn("def _is_operations_category", self.preview_source)
        self.assertNotIn("def _is_finance_category", self.preview_source)
        self.assertNotIn("\"technical\" in repair_category", self.preview_lower)
        self.assertNotIn("keyword in repair_category", self.preview_lower)

    def test_24_validator_and_preview_modules_remain_isolated(self) -> None:
        for module_text in [self.validator_lower, self.preview_lower]:
            tree = ast.parse(module_text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported = " ".join(alias.name for alias in node.names)
                    self.assertNotIn("fastapi", imported.lower())
                    self.assertNotIn("pymongo", imported.lower())
                    self.assertNotIn("motor", imported.lower())
                    self.assertNotIn("bson", imported.lower())
                    self.assertNotIn("pydantic", imported.lower())
                elif isinstance(node, ast.ImportFrom):
                    imported_from = (node.module or "").lower()
                    self.assertNotIn("fastapi", imported_from)
                    self.assertNotIn("pymongo", imported_from)
                    self.assertNotIn("motor", imported_from)
                    self.assertNotIn("bson", imported_from)
                    self.assertNotIn("pydantic", imported_from)
                    self.assertNotIn("backend.app.routes", imported_from)
                    self.assertNotIn("backend.app.services", imported_from)
                    self.assertNotIn("backend.scripts", imported_from)

            self.assertNotIn("backend.app.routes", module_text)
            self.assertNotIn("backend.app.services", module_text)
            self.assertNotIn("backend.scripts", module_text)

    def test_25_source_still_says_non_operational_guardrails(self) -> None:
        for module_lower in [self.validator_lower, self.preview_lower]:
            self.assertIn("does not execute repairs", module_lower)
            self.assertIn("does not write to the database", module_lower)
            self.assertIn("does not queue mint work", module_lower)
            self.assertIn("does not mutate certificates", module_lower)


if __name__ == "__main__":
    unittest.main()
