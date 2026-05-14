import ast
from importlib import import_module
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_feature_flags.py"
MODULE_IMPORT = "backend.app.core.continuity_kernel_feature_flags"
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6b_feature_flag_module.md"


class TestContinuityKernelPhase6BFeatureFlagModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module_exists = MODULE_PATH.exists()
        cls.module_text = MODULE_PATH.read_text(encoding="utf-8") if cls.module_exists else ""
        cls.module_lower = cls.module_text.lower()
        cls.module = import_module(MODULE_IMPORT) if cls.module_exists else None

        cls.doc_exists = DOC_PATH.exists()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if cls.doc_exists else ""
        cls.doc_lower = cls.doc_text.lower()

    def _runtime_candidates(self, *patterns: str) -> list[Path]:
        candidates: list[Path] = []
        for pattern in patterns:
            candidates.extend(path for path in REPO_ROOT.glob(pattern) if path.is_file())
        return candidates

    def _assert_not_imported_under(self, paths: list[Path]) -> None:
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            self.assertNotIn(
                "continuity_kernel_feature_flags",
                text,
                msg=f"Unexpected feature flag import in {path}",
            )

    def test_01_feature_flag_module_exists(self) -> None:
        self.assertTrue(self.module_exists)

    def test_02_module_imports_with_standard_library_only(self) -> None:
        self.assertTrue(self.module_exists)
        module_ast = ast.parse(self.module_text)

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
            self.assertIn(
                imported_root,
                sys.stdlib_module_names,
                msg=f"Non-stdlib import in feature flags module: {imported_root}",
            )

        prohibited_roots = {"fastapi", "pydantic", "pymongo", "motor", "bson", "stripe", "web3"}
        self.assertTrue(imported_roots.isdisjoint(prohibited_roots))

    def test_03_module_source_has_non_operational_guardrails(self) -> None:
        self.assertIn("this module is isolated.", self.module_lower)
        self.assertIn("this module does not wire runtime routes.", self.module_lower)
        self.assertIn("this module does not create apply mode.", self.module_lower)
        self.assertIn("this module does not execute repairs.", self.module_lower)
        self.assertIn("this module does not write to the database.", self.module_lower)
        self.assertIn("this module does not queue mint work.", self.module_lower)
        self.assertIn("this module does not mutate certificates.", self.module_lower)
        self.assertIn("this module does not alter customer records.", self.module_lower)

    def test_04_flag_constant_exists(self) -> None:
        self.assertEqual(
            self.module.CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED,
            "CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED",
        )

    def test_05_default_constant_is_false(self) -> None:
        self.assertIs(self.module.DEFAULT_CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED, False)

    def test_06_normalize_bool_flag_true_is_true(self) -> None:
        self.assertIs(self.module.normalize_bool_flag(True), True)

    def test_07_normalize_bool_flag_false_is_false(self) -> None:
        self.assertIs(self.module.normalize_bool_flag(False), False)

    def test_08_normalize_bool_flag_none_is_false(self) -> None:
        self.assertIs(self.module.normalize_bool_flag(None), False)

    def test_09_normalize_bool_flag_empty_string_is_false(self) -> None:
        self.assertIs(self.module.normalize_bool_flag(""), False)

    def test_10_true_like_strings_return_true(self) -> None:
        for value in ["1", "true", "yes", "on", "enabled"]:
            self.assertIs(self.module.normalize_bool_flag(value), True)
            self.assertIs(self.module.normalize_bool_flag(value.upper()), True)

    def test_11_false_like_strings_return_false(self) -> None:
        for value in ["0", "false", "no", "off", "disabled"]:
            self.assertIs(self.module.normalize_bool_flag(value), False)
            self.assertIs(self.module.normalize_bool_flag(value.upper()), False)

    def test_12_unknown_strings_return_false(self) -> None:
        for value in ["maybe", "truthy", "10", "enable"]:
            self.assertIs(self.module.normalize_bool_flag(value), False)

    def test_13_non_string_non_bool_values_return_false(self) -> None:
        for value in [0, 1, 2, [], {}, object()]:
            self.assertIs(self.module.normalize_bool_flag(value), False)

    def test_14_missing_env_flag_returns_false(self) -> None:
        self.assertIs(self.module.is_readonly_admin_preview_enabled(env={}), False)

    def test_15_invalid_env_flag_returns_false(self) -> None:
        env = {"CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED": "invalid-value"}
        self.assertIs(self.module.is_readonly_admin_preview_enabled(env=env), False)

    def test_16_explicit_true_env_flag_returns_true(self) -> None:
        for value in ["1", "true", "yes", "on", "enabled"]:
            env = {"CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED": value}
            self.assertIs(self.module.is_readonly_admin_preview_enabled(env=env), True)

    def test_17_feature_flag_status_has_required_keys(self) -> None:
        status = self.module.feature_flag_status(env={})
        self.assertEqual(
            set(status.keys()),
            {"flag_name", "enabled", "default", "source", "fail_closed"},
        )

    def test_18_feature_flag_status_default_is_false(self) -> None:
        status = self.module.feature_flag_status(env={})
        self.assertIs(status["default"], False)

    def test_19_feature_flag_status_fail_closed_is_true(self) -> None:
        status = self.module.feature_flag_status(env={})
        self.assertIs(status["fail_closed"], True)

    def test_20_module_not_imported_in_routes(self) -> None:
        self._assert_not_imported_under(self._runtime_candidates("backend/app/routes/**/*.py", "backend/app/routes/*.py"))

    def test_21_module_not_imported_in_services(self) -> None:
        self._assert_not_imported_under(self._runtime_candidates("backend/app/services/**/*.py", "backend/app/services/*.py"))

    def test_22_module_not_imported_in_scripts(self) -> None:
        self._assert_not_imported_under(self._runtime_candidates("backend/scripts/**/*.py", "backend/scripts/*.py"))

    def test_23_module_not_imported_in_app_main(self) -> None:
        app_main = REPO_ROOT / "backend" / "app" / "main.py"
        self.assertTrue(app_main.exists())
        self._assert_not_imported_under([app_main])

    def test_24_phase6b_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_25_doc_says_missing_false_off(self) -> None:
        self.assertIn("missing = false/off", self.doc_lower)

    def test_26_doc_says_invalid_false_off(self) -> None:
        self.assertIn("invalid = false/off", self.doc_lower)

    def test_27_doc_says_production_default_false_off(self) -> None:
        self.assertIn("production default = false/off", self.doc_lower)

    def test_28_doc_says_not_wired_into_routes_services(self) -> None:
        self.assertIn("phase 6b does not wire the flag into routes", self.doc_lower)
        self.assertIn("phase 6b does not wire the flag into services", self.doc_lower)

    def test_29_doc_says_no_apply_mode_or_repair_scripts(self) -> None:
        self.assertIn("phase 6b does not create apply mode", self.doc_lower)
        self.assertIn("phase 6b does not create repair scripts", self.doc_lower)


if __name__ == "__main__":
    unittest.main()
