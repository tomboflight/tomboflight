from pathlib import Path
import ast
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase5p_prewiring_readiness.md"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
ARCH_TESTS_DIR = REPO_ROOT / "backend" / "tests" / "architecture"
CONTRACT_TESTS_DIR = REPO_ROOT / "backend" / "tests" / "contracts"

KERNEL_MODULES = {
    "continuity_kernel_taxonomy.py": REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_taxonomy.py",
    "continuity_kernel_validator.py": REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_validator.py",
    "continuity_kernel_dry_run_adapter.py": REPO_ROOT
    / "backend"
    / "app"
    / "core"
    / "continuity_kernel_dry_run_adapter.py",
    "continuity_kernel_admin_preview.py": REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_admin_preview.py",
}

REQUIRED_GOVERNANCE_DOCS = {
    "tomb_of_light_continuity_kernel.md": REPO_ROOT
    / "backend"
    / "docs"
    / "architecture"
    / "tomb_of_light_continuity_kernel.md",
    "tol_continuity_kernel_inventory.md": REPO_ROOT / "backend" / "docs" / "audits" / "tol_continuity_kernel_inventory.md",
    "tol_continuity_kernel_next_tasks.md": REPO_ROOT / "backend" / "docs" / "audits" / "tol_continuity_kernel_next_tasks.md",
    "continuity_kernel_phase3_contracts.md": REPO_ROOT
    / "backend"
    / "docs"
    / "contracts"
    / "continuity_kernel_phase3_contracts.md",
    "continuity_kernel_phase4_dry_run_repair_plans.md": REPO_ROOT
    / "backend"
    / "docs"
    / "repair"
    / "continuity_kernel_phase4_dry_run_repair_plans.md",
    "continuity_kernel_phase5a_apply_governance.md": REPO_ROOT
    / "backend"
    / "docs"
    / "governance"
    / "continuity_kernel_phase5a_apply_governance.md",
    "continuity_kernel_phase5b_apply_contracts.md": REPO_ROOT
    / "backend"
    / "docs"
    / "governance"
    / "continuity_kernel_phase5b_apply_contracts.md",
    "continuity_kernel_phase5c_validator_schema.md": REPO_ROOT
    / "backend"
    / "docs"
    / "governance"
    / "continuity_kernel_phase5c_validator_schema.md",
    "continuity_kernel_phase5e_cross_payload_consistency.md": REPO_ROOT
    / "backend"
    / "docs"
    / "governance"
    / "continuity_kernel_phase5e_cross_payload_consistency.md",
    "continuity_kernel_phase5f_structured_overrides.md": REPO_ROOT
    / "backend"
    / "docs"
    / "governance"
    / "continuity_kernel_phase5f_structured_overrides.md",
    "continuity_kernel_phase5g_payload_placement.md": REPO_ROOT
    / "backend"
    / "docs"
    / "governance"
    / "continuity_kernel_phase5g_payload_placement.md",
    "continuity_kernel_phase5h_ci_enforcement.md": REPO_ROOT
    / "backend"
    / "docs"
    / "governance"
    / "continuity_kernel_phase5h_ci_enforcement.md",
    "continuity_kernel_phase5i_staging_dry_run_adapter.md": REPO_ROOT
    / "backend"
    / "docs"
    / "governance"
    / "continuity_kernel_phase5i_staging_dry_run_adapter.md",
    "continuity_kernel_phase5k_readonly_admin_preview.md": REPO_ROOT
    / "backend"
    / "docs"
    / "governance"
    / "continuity_kernel_phase5k_readonly_admin_preview.md",
    "continuity_kernel_phase5m_role_category_taxonomy.md": REPO_ROOT
    / "backend"
    / "docs"
    / "governance"
    / "continuity_kernel_phase5m_role_category_taxonomy.md",
    "continuity_kernel_phase5n_shared_taxonomy.md": REPO_ROOT
    / "backend"
    / "docs"
    / "governance"
    / "continuity_kernel_phase5n_shared_taxonomy.md",
    "continuity_kernel_phase5o_direct_import_cleanup.md": REPO_ROOT
    / "backend"
    / "docs"
    / "governance"
    / "continuity_kernel_phase5o_direct_import_cleanup.md",
}

KERNEL_MODULE_IMPORT_TOKENS = [
    "continuity_kernel_taxonomy",
    "continuity_kernel_validator",
    "continuity_kernel_dry_run_adapter",
    "continuity_kernel_admin_preview",
]

FORBIDDEN_RUNTIME_IMPORTS = (
    "fastapi",
    "pydantic",
    "pymongo",
    "motor",
    "bson",
    "stripe",
    "web3",
    "backend.app.routes",
    "backend.app.services",
    "backend.scripts",
)

DB_WRITE_TOKENS = (
    "insert_one",
    "update_one",
    "update_many",
    "delete_one",
    "delete_many",
    "replace_one",
    "bulk_write",
)

OBVIOUS_MINT_QUEUE_EXECUTION_TOKENS = (
    "queue_mint(",
    "enqueue_mint",
    "mint_queue.",
    "mintqueue.",
    "queue_mint_work(",
)

EXECUTABLE_REPAIR_ENTRYPOINT_TOKENS = (
    'if __name__ == "__main__"',
    "argparse",
    "click.command",
)

NON_OPERATIONAL_GUARDRAIL_TOKENS = (
    "does not execute repairs",
    "does not write to the database",
    "does not queue mint work",
)


class TestContinuityKernelPhase5PPrewiringReadiness(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_exists = DOC_PATH.exists()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if cls.doc_exists else ""
        cls.doc_lower = cls.doc_text.lower()
        cls.workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8") if WORKFLOW_PATH.exists() else ""
        cls.workflow_lower = cls.workflow_text.lower()

        cls.kernel_sources: dict[str, str] = {}
        cls.kernel_lowers: dict[str, str] = {}
        for module_name, module_path in KERNEL_MODULES.items():
            source = module_path.read_text(encoding="utf-8")
            cls.kernel_sources[module_name] = source
            cls.kernel_lowers[module_name] = source.lower()

    def _runtime_candidates(self, path_pattern: str) -> list[Path]:
        return [path for path in REPO_ROOT.glob(path_pattern) if path.is_file()]

    def _assert_kernel_not_imported_under(self, paths: list[Path]) -> None:
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for token in KERNEL_MODULE_IMPORT_TOKENS:
                self.assertNotIn(token, text, msg=f"Unexpected kernel import token '{token}' in {path}")

    def _assert_kernel_modules_do_not_import_prefixes(self, forbidden_prefixes: tuple[str, ...]) -> None:
        for module_name, source in self.kernel_sources.items():
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported = alias.name.lower()
                        self.assertFalse(
                            any(imported.startswith(prefix) for prefix in forbidden_prefixes),
                            msg=f"Forbidden import found in {module_name}: {alias.name}",
                        )
                elif isinstance(node, ast.ImportFrom):
                    imported_from = (node.module or "").lower()
                    self.assertFalse(
                        any(imported_from.startswith(prefix) for prefix in forbidden_prefixes),
                        msg=f"Forbidden import-from found in {module_name}: {imported_from}",
                    )

    def test_01_phase5p_readiness_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_all_four_kernel_modules_exist(self) -> None:
        for module_name, module_path in KERNEL_MODULES.items():
            self.assertTrue(module_path.exists(), msg=f"Missing kernel module: {module_name}")

    def test_03_all_required_governance_docs_exist(self) -> None:
        for doc_name, doc_path in REQUIRED_GOVERNANCE_DOCS.items():
            self.assertTrue(doc_path.exists(), msg=f"Missing required governance doc: {doc_name}")

    def test_04_architecture_tests_directory_exists(self) -> None:
        self.assertTrue(ARCH_TESTS_DIR.exists() and ARCH_TESTS_DIR.is_dir())

    def test_05_contracts_tests_directory_exists(self) -> None:
        self.assertTrue(CONTRACT_TESTS_DIR.exists() and CONTRACT_TESTS_DIR.is_dir())

    def test_06_ci_workflow_exists(self) -> None:
        self.assertTrue(WORKFLOW_PATH.exists())

    def test_07_ci_workflow_includes_compileall_command(self) -> None:
        self.assertIn("python -m compileall backend/app backend/scripts", self.workflow_text)

    def test_08_ci_workflow_includes_architecture_test_command(self) -> None:
        self.assertIn('python -m unittest discover -s backend/tests/architecture -p "test_*.py" -v', self.workflow_text)

    def test_09_ci_workflow_includes_contracts_test_command(self) -> None:
        self.assertIn('python -m unittest discover -s backend/tests/contracts -p "test_*.py" -v', self.workflow_text)

    def test_10_ci_workflow_uses_contents_read_permission(self) -> None:
        self.assertIn("contents: read", self.workflow_lower)

    def test_11_kernel_modules_not_imported_in_routes(self) -> None:
        self._assert_kernel_not_imported_under(self._runtime_candidates("backend/app/routes/**/*.py"))

    def test_12_kernel_modules_not_imported_in_services(self) -> None:
        self._assert_kernel_not_imported_under(self._runtime_candidates("backend/app/services/**/*.py"))

    def test_13_kernel_modules_not_imported_in_scripts(self) -> None:
        self._assert_kernel_not_imported_under(self._runtime_candidates("backend/scripts/**/*.py"))

    def test_14_kernel_modules_not_imported_in_app_main(self) -> None:
        app_main = REPO_ROOT / "backend" / "app" / "main.py"
        self.assertTrue(app_main.exists(), msg="backend/app/main.py must exist for this assertion")
        self._assert_kernel_not_imported_under([app_main])

    def test_15_kernel_modules_do_not_import_fastapi(self) -> None:
        self._assert_kernel_modules_do_not_import_prefixes(("fastapi",))

    def test_16_kernel_modules_do_not_import_pydantic(self) -> None:
        self._assert_kernel_modules_do_not_import_prefixes(("pydantic",))

    def test_17_kernel_modules_do_not_import_pymongo_motor_or_bson(self) -> None:
        self._assert_kernel_modules_do_not_import_prefixes(("pymongo", "motor", "bson"))

    def test_18_kernel_modules_do_not_import_stripe_or_web3(self) -> None:
        self._assert_kernel_modules_do_not_import_prefixes(("stripe", "web3"))

    def test_19_kernel_modules_do_not_import_backend_app_routes(self) -> None:
        self._assert_kernel_modules_do_not_import_prefixes(("backend.app.routes",))

    def test_20_kernel_modules_do_not_import_backend_app_services(self) -> None:
        self._assert_kernel_modules_do_not_import_prefixes(("backend.app.services",))

    def test_21_kernel_modules_do_not_import_backend_scripts(self) -> None:
        self._assert_kernel_modules_do_not_import_prefixes(("backend.scripts",))

    def test_22_kernel_modules_do_not_contain_obvious_database_write_calls(self) -> None:
        for module_name, source_lower in self.kernel_lowers.items():
            for token in DB_WRITE_TOKENS:
                self.assertNotIn(token, source_lower, msg=f"Database write token '{token}' found in {module_name}")

    def test_23_kernel_modules_do_not_contain_obvious_mint_queue_execution_language(self) -> None:
        for module_name, source_lower in self.kernel_lowers.items():
            for token in OBVIOUS_MINT_QUEUE_EXECUTION_TOKENS:
                self.assertNotIn(token, source_lower, msg=f"Mint queue execution token '{token}' found in {module_name}")

    def test_24_kernel_modules_do_not_contain_executable_repair_script_entrypoints(self) -> None:
        for module_name, source_lower in self.kernel_lowers.items():
            for token in EXECUTABLE_REPAIR_ENTRYPOINT_TOKENS:
                self.assertNotIn(token, source_lower, msg=f"Executable repair token '{token}' found in {module_name}")

    def test_25_kernel_module_docstrings_contain_non_operational_guardrail_language(self) -> None:
        for module_name, source_lower in self.kernel_lowers.items():
            for token in NON_OPERATIONAL_GUARDRAIL_TOKENS:
                self.assertIn(token, source_lower, msg=f"Missing guardrail token '{token}' in {module_name}")

    def test_26_no_backend_script_with_continuity_kernel_repair_apply_pattern_exists(self) -> None:
        for script_path in self._runtime_candidates("backend/scripts/**/*.py"):
            stem = script_path.stem.lower()
            disallowed = "continuity_kernel" in stem and ("repair" in stem or "apply" in stem)
            self.assertFalse(disallowed, msg=f"Disallowed continuity kernel repair/apply script found: {script_path}")

    def test_27_phase5p_doc_says_phase5p_does_not_approve_runtime_wiring_by_itself(self) -> None:
        self.assertIn("phase 5p does not approve runtime wiring by itself", self.doc_lower)

    def test_28_phase5p_doc_says_phase6_runtime_admin_wiring_must_be_separately_approved_and_read_only_first(self) -> None:
        self.assertIn("must be separately approved", self.doc_lower)
        self.assertIn("read-only first", self.doc_lower)


if __name__ == "__main__":
    unittest.main()
