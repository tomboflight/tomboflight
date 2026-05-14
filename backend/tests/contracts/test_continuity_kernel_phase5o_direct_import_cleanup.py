from importlib import import_module
from pathlib import Path
import ast
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase5o_direct_import_cleanup.md"
PREVIEW_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_admin_preview.py"
VALIDATOR_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_validator.py"
ADAPTER_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_dry_run_adapter.py"
TAXONOMY_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_taxonomy.py"


class TestContinuityKernelPhase5ODirectImportCleanup(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_exists = DOC_PATH.exists()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if cls.doc_exists else ""
        cls.doc_lower = cls.doc_text.lower()

        cls.preview_source = PREVIEW_PATH.read_text(encoding="utf-8")
        cls.preview_lower = cls.preview_source.lower()
        cls.validator_source = VALIDATOR_PATH.read_text(encoding="utf-8")
        cls.validator_lower = cls.validator_source.lower()
        cls.adapter_source = ADAPTER_PATH.read_text(encoding="utf-8")
        cls.adapter_lower = cls.adapter_source.lower()
        cls.taxonomy_source = TAXONOMY_PATH.read_text(encoding="utf-8")
        cls.taxonomy_lower = cls.taxonomy_source.lower()

        cls.preview = import_module("backend.app.core.continuity_kernel_admin_preview")
        cls.validator = import_module("backend.app.core.continuity_kernel_validator")

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
            "policy_source": "phase5o-tests",
            "evaluated_at": "2099-01-01T00:00:00Z",
        }

    def _assert_no_forbidden_imports(self, source: str) -> None:
        forbidden_prefixes = [
            "fastapi",
            "pymongo",
            "motor",
            "bson",
            "pydantic",
            "stripe",
            "web3",
            "backend.app.routes",
            "backend.app.services",
            "backend.scripts",
            "backend.app.db",
            "backend.app.database",
            "backend.database",
            "backend.db",
        ]

        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name.lower()
                    self.assertFalse(
                        any(imported.startswith(prefix) for prefix in forbidden_prefixes),
                        msg=f"Forbidden import found: {alias.name}",
                    )
                    self.assertFalse(imported.startswith("backend") and ".session" in imported)
            elif isinstance(node, ast.ImportFrom):
                imported_from = (node.module or "").lower()
                self.assertFalse(
                    any(imported_from.startswith(prefix) for prefix in forbidden_prefixes),
                    msg=f"Forbidden import-from found: {imported_from}",
                )
                self.assertFalse(imported_from.startswith("backend") and ".session" in imported_from)

    def _runtime_candidates(self) -> list[Path]:
        candidates: list[Path] = []
        for pattern in [
            "backend/app/routes/**/*.py",
            "backend/app/services/**/*.py",
            "backend/scripts/**/*.py",
        ]:
            candidates.extend(REPO_ROOT.glob(pattern))

        for explicit in [
            REPO_ROOT / "backend" / "main.py",
            REPO_ROOT / "backend" / "app" / "main.py",
        ]:
            if explicit.exists():
                candidates.append(explicit)
        return candidates

    def test_01_phase5o_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_lists_approved_isolated_core_modules(self) -> None:
        for module_name in [
            "backend.app.core.continuity_kernel_taxonomy",
            "backend.app.core.continuity_kernel_validator",
            "backend.app.core.continuity_kernel_dry_run_adapter",
            "backend.app.core.continuity_kernel_admin_preview",
        ]:
            self.assertIn(module_name, self.doc_text)

    def test_03_doc_lists_forbidden_imports(self) -> None:
        for value in [
            "fastapi",
            "pymongo",
            "motor",
            "bson",
            "pydantic",
            "stripe",
            "web3",
            "backend.app.routes",
            "backend.app.services",
            "backend.scripts",
            "database/session modules",
        ]:
            self.assertIn(value, self.doc_lower)

    def test_04_doc_says_direct_imports_between_approved_core_modules_are_allowed(self) -> None:
        self.assertIn("may directly import another approved continuity kernel core module", self.doc_lower)

    def test_05_doc_says_routes_services_scripts_main_must_not_import_continuity_kernel_yet(self) -> None:
        self.assertIn("routes/services/scripts/main must not import continuity kernel modules yet", self.doc_lower)

    def test_06_admin_preview_uses_direct_taxonomy_import_without_importlib_indirection(self) -> None:
        self.assertIn("from backend.app.core.continuity_kernel_taxonomy import", self.preview_source)
        self.assertNotIn('import_module("backend.app.core.continuity_kernel_taxonomy")', self.preview_source)
        self.assertNotIn("from importlib import import_module", self.preview_source)

    def test_07_admin_preview_still_does_not_import_forbidden_external_runtime_dependencies(self) -> None:
        self._assert_no_forbidden_imports(self.preview_source)

    def test_08_admin_preview_still_does_not_import_routes_services_scripts_database_modules(self) -> None:
        for forbidden in [
            "backend.app.routes",
            "backend.app.services",
            "backend.scripts",
            "backend.app.db",
            "backend.app.database",
            ".session",
        ]:
            self.assertNotIn(forbidden, self.preview_lower)

    def test_09_validator_still_does_not_import_forbidden_runtime_external_modules(self) -> None:
        self._assert_no_forbidden_imports(self.validator_source)

    def test_10_dry_run_adapter_still_does_not_import_forbidden_runtime_external_modules(self) -> None:
        self._assert_no_forbidden_imports(self.adapter_source)

    def test_11_taxonomy_module_still_does_not_import_forbidden_runtime_external_modules(self) -> None:
        self._assert_no_forbidden_imports(self.taxonomy_source)

    def test_12_routes_services_scripts_main_still_do_not_import_continuity_kernel_modules(self) -> None:
        forbidden_modules = [
            "continuity_kernel_validator",
            "continuity_kernel_dry_run_adapter",
            "continuity_kernel_admin_preview",
            "continuity_kernel_taxonomy",
        ]
        for path in self._runtime_candidates():
            text = path.read_text(encoding="utf-8", errors="ignore")
            lowered = text.lower()
            for module_name in forbidden_modules:
                self.assertNotIn(module_name, lowered, msg=f"Unexpected Continuity Kernel reference in {path}: {module_name}")

    def test_13_preview_behavior_remains_fail_closed_and_prohibited_actions_never_returned(self) -> None:
        self.assertEqual(self.preview.allowed_preview_actions_for_role("unknown_role", "workspace_membership_repair"), [])
        self.assertEqual(self.preview.allowed_preview_actions_for_role("SUPERADMIN", "unknown_category"), [])
        self.assertEqual(self.preview.allowed_preview_actions_for_role("marketing_admin", "workspace_membership_repair"), [])
        self.assertEqual(self.preview.allowed_preview_actions_for_role("CMO", "workspace_membership_repair"), [])

        prohibited = set(self.preview.PROHIBITED_ACTIONS)
        for role in list(self.preview.CANONICAL_OFFICER_ROLES) + ["unknown_role"]:
            for category in list(self.preview.CANONICAL_REPAIR_CATEGORIES) + ["unknown_category"]:
                actions = self.preview.allowed_preview_actions_for_role(role, category)
                self.assertTrue(set(actions).isdisjoint(prohibited), msg=f"Prohibited action returned for {role}/{category}")

    def test_14_validator_behavior_remains_fail_closed_for_unknown_and_marketing_roles(self) -> None:
        self.assertFalse(
            self.validator.validate_authorization_decision(
                self._authorization("unknown_role", "workspace_membership_repair")
            )["passed"]
        )
        self.assertFalse(
            self.validator.validate_authorization_decision(self._authorization("SUPERADMIN", "unknown_category"))["passed"]
        )
        self.assertFalse(
            self.validator.validate_authorization_decision(
                self._authorization("marketing_admin", "workspace_membership_repair")
            )["passed"]
        )
        self.assertFalse(
            self.validator.validate_authorization_decision(self._authorization("CMO", "workspace_membership_repair"))["passed"]
        )

    def test_15_source_still_contains_non_operational_guardrails(self) -> None:
        module_sources = {
            str(PREVIEW_PATH): self.preview_lower,
            str(VALIDATOR_PATH): self.validator_lower,
            str(ADAPTER_PATH): self.adapter_lower,
            str(TAXONOMY_PATH): self.taxonomy_lower,
        }
        for module_path, source_lower in module_sources.items():
            with self.subTest(module=module_path):
                self.assertIn("does not execute repairs", source_lower)
                self.assertIn("does not write to the database", source_lower)
                self.assertIn("does not queue mint work", source_lower)
                self.assertIn("does not mutate certificates", source_lower)


if __name__ == "__main__":
    unittest.main()
