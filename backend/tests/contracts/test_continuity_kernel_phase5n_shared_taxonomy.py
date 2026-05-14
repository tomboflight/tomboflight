from importlib import import_module
from pathlib import Path
import ast
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
TAXONOMY_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_taxonomy.py"
VALIDATOR_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_validator.py"
PREVIEW_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_admin_preview.py"


class TestContinuityKernelPhase5NSharedTaxonomy(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.taxonomy_exists = TAXONOMY_PATH.exists()
        cls.validator_source = VALIDATOR_PATH.read_text(encoding="utf-8")
        cls.preview_source = PREVIEW_PATH.read_text(encoding="utf-8")
        cls.taxonomy_source = TAXONOMY_PATH.read_text(encoding="utf-8") if cls.taxonomy_exists else ""

        cls.taxonomy = import_module("backend.app.core.continuity_kernel_taxonomy")
        cls.validator = import_module("backend.app.core.continuity_kernel_validator")
        cls.preview = import_module("backend.app.core.continuity_kernel_admin_preview")

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
            "policy_source": "phase5n-tests",
            "evaluated_at": "2099-01-01T00:00:00Z",
        }

    def test_01_shared_taxonomy_module_exists(self) -> None:
        self.assertTrue(self.taxonomy_exists)

    def test_02_shared_taxonomy_module_imports_with_standard_library_only(self) -> None:
        stdlib_names = set(getattr(sys, "stdlib_module_names", set()))
        tree = ast.parse(self.taxonomy_source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    self.assertIn(root, stdlib_names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                module_name = node.module or ""
                root = module_name.split(".")[0]
                self.assertIn(root, stdlib_names)

    def test_03_shared_taxonomy_module_docstring_says_isolated_taxonomy_only_and_non_operational(self) -> None:
        module_doc = self.taxonomy.__doc__ or ""
        doc_lower = module_doc.lower()
        self.assertIn("isolated taxonomy only", doc_lower)
        self.assertIn("non-operational", doc_lower)
        self.assertIn("does not execute repairs", doc_lower)
        self.assertIn("does not write to the database", doc_lower)
        self.assertIn("does not queue mint work", doc_lower)
        self.assertIn("does not mutate certificates", doc_lower)
        self.assertIn("does not alter customer records", doc_lower)

    def test_04_all_canonical_officer_roles_exist_in_taxonomy(self) -> None:
        for role in [
            "SUPERADMIN",
            "EXECUTIVE_TECH_ADMIN",
            "operations_admin",
            "finance_admin",
            "marketing_admin",
            "CMO",
        ]:
            self.assertIn(role, self.taxonomy.CANONICAL_OFFICER_ROLES)

    def test_05_all_canonical_repair_categories_exist_in_taxonomy(self) -> None:
        for category in [
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
            self.assertIn(category, self.taxonomy.CANONICAL_REPAIR_CATEGORIES)

    def test_06_all_category_groups_exist_in_taxonomy(self) -> None:
        for attr in [
            "TECHNICAL_CATEGORIES",
            "OPERATIONS_CATEGORIES",
            "FINANCE_CATEGORIES",
            "MARKETING_CATEGORIES",
            "SUPERADMIN_ONLY_CATEGORIES",
            "READ_ONLY_PREVIEW_CATEGORIES",
        ]:
            self.assertTrue(hasattr(self.taxonomy, attr))

    def test_07_role_to_allowed_categories_exists(self) -> None:
        self.assertTrue(hasattr(self.taxonomy, "ROLE_TO_ALLOWED_CATEGORIES"))

    def test_08_role_to_preview_categories_exists(self) -> None:
        self.assertTrue(hasattr(self.taxonomy, "ROLE_TO_PREVIEW_CATEGORIES"))

    def test_09_unknown_role_returns_empty_allowed_categories(self) -> None:
        self.assertEqual(self.taxonomy.allowed_categories_for_role("unknown_role"), frozenset())

    def test_10_unknown_role_returns_empty_preview_categories(self) -> None:
        self.assertEqual(self.taxonomy.preview_categories_for_role("unknown_role"), frozenset())

    def test_11_unknown_category_is_not_canonical(self) -> None:
        self.assertFalse(self.taxonomy.is_canonical_repair_category("unknown_category"))

    def test_12_marketing_admin_and_cmo_have_no_approval_categories(self) -> None:
        self.assertEqual(self.taxonomy.allowed_categories_for_role("marketing_admin"), frozenset())
        self.assertEqual(self.taxonomy.allowed_categories_for_role("CMO"), frozenset())

    def test_13_superadmin_allowed_categories_include_all_canonical_categories(self) -> None:
        self.assertEqual(
            self.taxonomy.allowed_categories_for_role("SUPERADMIN"),
            frozenset(self.taxonomy.CANONICAL_REPAIR_CATEGORIES),
        )

    def test_14_finance_admin_allowed_categories_equal_finance_categories(self) -> None:
        self.assertEqual(
            self.taxonomy.allowed_categories_for_role("finance_admin"),
            self.taxonomy.FINANCE_CATEGORIES,
        )

    def test_15_operations_admin_allowed_categories_equal_operations_categories(self) -> None:
        self.assertEqual(
            self.taxonomy.allowed_categories_for_role("operations_admin"),
            self.taxonomy.OPERATIONS_CATEGORIES,
        )

    def test_16_preview_categories_are_explicit_and_do_not_include_unknown_categories(self) -> None:
        unknown = "unknown_category"
        for role in self.taxonomy.CANONICAL_OFFICER_ROLES:
            categories = self.taxonomy.preview_categories_for_role(role)
            self.assertTrue(categories.issubset(set(self.taxonomy.CANONICAL_REPAIR_CATEGORIES)))
            self.assertNotIn(unknown, categories)

    def test_17_validator_imports_taxonomy_module(self) -> None:
        self.assertIn("continuity_kernel_taxonomy", self.validator_source)

    def test_18_preview_imports_taxonomy_module(self) -> None:
        self.assertIn("continuity_kernel_taxonomy", self.preview_source)

    def test_19_validator_duplicate_category_groups_if_present_are_identical_to_taxonomy(self) -> None:
        for attr in [
            "CANONICAL_OFFICER_ROLES",
            "CANONICAL_REPAIR_CATEGORIES",
            "TECHNICAL_CATEGORIES",
            "OPERATIONS_CATEGORIES",
            "FINANCE_CATEGORIES",
            "MARKETING_CATEGORIES",
            "SUPERADMIN_ONLY_CATEGORIES",
            "ROLE_TO_ALLOWED_CATEGORIES",
        ]:
            self.assertEqual(getattr(self.validator, attr), getattr(self.taxonomy, attr))

    def test_20_preview_duplicate_category_groups_if_present_are_identical_to_taxonomy(self) -> None:
        for attr in [
            "CANONICAL_OFFICER_ROLES",
            "CANONICAL_REPAIR_CATEGORIES",
            "TECHNICAL_CATEGORIES",
            "OPERATIONS_CATEGORIES",
            "FINANCE_CATEGORIES",
            "MARKETING_CATEGORIES",
            "SUPERADMIN_ONLY_CATEGORIES",
            "ROLE_TO_PREVIEW_CATEGORIES",
        ]:
            self.assertEqual(getattr(self.preview, attr), getattr(self.taxonomy, attr))

    def test_21_validator_unknown_role_still_fails_closed(self) -> None:
        result = self.validator.validate_authorization_decision(
            self._authorization("unknown_role", "workspace_membership_repair")
        )
        self.assertFalse(result["passed"])

    def test_22_validator_unknown_category_still_fails_closed(self) -> None:
        result = self.validator.validate_authorization_decision(self._authorization("SUPERADMIN", "unknown_category"))
        self.assertFalse(result["passed"])

    def test_23_preview_unknown_role_still_returns_no_actions(self) -> None:
        self.assertEqual(
            self.preview.allowed_preview_actions_for_role("unknown_role", "workspace_membership_repair"),
            [],
        )

    def test_24_preview_unknown_category_still_returns_no_actions(self) -> None:
        self.assertEqual(
            self.preview.allowed_preview_actions_for_role("SUPERADMIN", "unknown_category"),
            [],
        )

    def test_25_modules_remain_isolated(self) -> None:
        for source in [self.taxonomy_source, self.validator_source, self.preview_source]:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_names = " ".join(alias.name.lower() for alias in node.names)
                    for forbidden in ["fastapi", "pymongo", "motor", "bson", "pydantic"]:
                        self.assertNotIn(forbidden, imported_names)
                elif isinstance(node, ast.ImportFrom):
                    imported_from = (node.module or "").lower()
                    for forbidden in ["fastapi", "pymongo", "motor", "bson", "pydantic"]:
                        self.assertNotIn(forbidden, imported_from)
                    self.assertNotIn("backend.app.routes", imported_from)
                    self.assertNotIn("backend.app.services", imported_from)
                    self.assertNotIn("backend.scripts", imported_from)

            lower = source.lower()
            self.assertNotIn("backend.app.routes", lower)
            self.assertNotIn("backend.app.services", lower)
            self.assertNotIn("backend.scripts", lower)


if __name__ == "__main__":
    unittest.main()
