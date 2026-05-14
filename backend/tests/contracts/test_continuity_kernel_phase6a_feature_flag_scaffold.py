import ast
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6a_feature_flag_scaffold.md"
FEATURE_FLAG_MODULE_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_feature_flags.py"

KERNEL_MODULE_IMPORT_TOKENS = [
    "continuity_kernel_taxonomy",
    "continuity_kernel_validator",
    "continuity_kernel_dry_run_adapter",
    "continuity_kernel_admin_preview",
]


class TestContinuityKernelPhase6AFeatureFlagScaffold(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_exists = DOC_PATH.exists()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if cls.doc_exists else ""
        cls.doc_lower = cls.doc_text.lower()

    def _runtime_candidates(self, *patterns: str) -> list[Path]:
        candidates: list[Path] = []
        for pattern in patterns:
            candidates.extend(path for path in REPO_ROOT.glob(pattern) if path.is_file())
        return candidates

    def _assert_kernel_not_imported_under(self, paths: list[Path]) -> None:
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for token in KERNEL_MODULE_IMPORT_TOKENS:
                self.assertNotIn(token, text, msg=f"Unexpected kernel import token '{token}' in {path}")

    def test_01_phase6a_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_includes_feature_flag_name(self) -> None:
        self.assertIn("continuity_kernel_readonly_admin_preview_enabled", self.doc_lower)

    def test_03_doc_says_default_is_false_off(self) -> None:
        self.assertIn("default is false/off", self.doc_lower)

    def test_04_doc_says_production_default_is_false_off(self) -> None:
        self.assertIn("production default is false/off", self.doc_lower)

    def test_05_doc_says_missing_flag_evaluates_false_off(self) -> None:
        self.assertIn("missing flag must evaluate false/off", self.doc_lower)

    def test_06_doc_says_invalid_flag_evaluates_false_off(self) -> None:
        self.assertIn("invalid flag value must evaluate false/off", self.doc_lower)

    def test_07_doc_says_flag_only_controls_future_read_only_admin_preview(self) -> None:
        self.assertIn("flag may only control future read-only admin preview", self.doc_lower)

    def test_08_doc_says_flag_must_not_enable_apply_mode(self) -> None:
        self.assertIn("flag must not enable apply mode", self.doc_lower)

    def test_09_doc_says_flag_must_not_enable_repair_execution(self) -> None:
        self.assertIn("flag must not enable repair execution", self.doc_lower)

    def test_10_doc_says_flag_must_not_enable_database_writes(self) -> None:
        self.assertIn("flag must not enable database writes", self.doc_lower)

    def test_11_doc_says_flag_must_not_enable_mint_queueing(self) -> None:
        self.assertIn("flag must not enable mint queueing", self.doc_lower)

    def test_12_doc_says_flag_must_not_enable_certificate_customer_mutation(self) -> None:
        self.assertIn("flag must not enable certificate/customer mutation", self.doc_lower)

    def test_13_doc_says_no_customer_facing_behavior(self) -> None:
        self.assertIn("flag must not expose customer-facing behavior", self.doc_lower)

    def test_14_doc_says_phase6a_adds_no_route_service_admin_ui_wiring(self) -> None:
        self.assertIn("no route wiring", self.doc_lower)
        self.assertIn("no service wiring", self.doc_lower)
        self.assertIn("no admin ui wiring", self.doc_lower)

    def test_15_existing_kernel_modules_remain_not_imported_in_routes(self) -> None:
        self._assert_kernel_not_imported_under(self._runtime_candidates("backend/app/routes/**/*.py", "backend/app/routes/*.py"))

    def test_16_existing_kernel_modules_remain_not_imported_in_services(self) -> None:
        self._assert_kernel_not_imported_under(self._runtime_candidates("backend/app/services/**/*.py", "backend/app/services/*.py"))

    def test_17_existing_kernel_modules_remain_not_imported_in_scripts(self) -> None:
        self._assert_kernel_not_imported_under(self._runtime_candidates("backend/scripts/**/*.py", "backend/scripts/*.py"))

    def test_18_existing_kernel_modules_remain_not_imported_in_app_main(self) -> None:
        app_main = REPO_ROOT / "backend" / "app" / "main.py"
        self.assertTrue(app_main.exists(), msg="backend/app/main.py must exist for this assertion")
        self._assert_kernel_not_imported_under([app_main])

    def test_19_optional_feature_flag_constants_module_contract(self) -> None:
        if not FEATURE_FLAG_MODULE_PATH.exists():
            self.skipTest("Optional feature-flag constants module not created in Phase 6A scaffold")

        module_text = FEATURE_FLAG_MODULE_PATH.read_text(encoding="utf-8")
        module_lower = module_text.lower()
        module_ast = ast.parse(module_text)

        imported_roots: set[str] = set()
        for node in ast.walk(module_ast):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_roots.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".")[0])

        for imported_root in imported_roots:
            if imported_root == "__future__":
                continue
            self.assertIn(imported_root, sys.stdlib_module_names, msg=f"Non-stdlib import in feature flags module: {imported_root}")

        prohibited_roots = {"fastapi", "pydantic", "pymongo", "motor", "stripe", "web3"}
        self.assertTrue(imported_roots.isdisjoint(prohibited_roots), msg="Feature flags module imported prohibited runtime dependencies")

        self.assertIn("continuity_kernel_readonly_admin_preview_enabled", module_lower)
        self.assertIn("false", module_lower)

        self.assertRegex(module_lower, r"missing[^\n]*false")
        self.assertRegex(module_lower, r"\bnone\b[^\n]*false")
        self.assertRegex(module_lower, r"invalid[^\n]*false")


if __name__ == "__main__":
    unittest.main()
