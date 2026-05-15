import ast
from importlib import import_module
from importlib.util import find_spec
import os
from pathlib import Path
import subprocess
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6l_runtime_no_skip_enforcement.md"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
HELPER_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_readonly_helper.py"
SCRIPTS_PATH = REPO_ROOT / "backend" / "scripts"

ENFORCE_NO_SKIP_ENV = "CONTINUITY_KERNEL_RUNTIME_TEST_ENFORCE_NO_SKIPS"
PHASE6I_MODULE = "backend.tests.contracts.test_continuity_kernel_phase6i_runtime_route_verification"
PHASE6I_FOCUSED_RUNTIME_TEST_COMMAND = (
    "python -m unittest backend.tests.contracts.test_continuity_kernel_phase6i_runtime_route_verification -v"
)
PHASE6L_NO_SKIP_COMMAND = (
    "python -m unittest backend.tests.contracts.test_continuity_kernel_phase6l_runtime_no_skip_enforcement -v"
)

DB_WRITE_TOKENS = (
    "insert_one(",
    "update_one(",
    "update_many(",
    "delete_one(",
    "delete_many(",
    "replace_one(",
    "bulk_write(",
)

PROHIBITED_EXEC_TOKENS = (
    "approve_apply(",
    "schedule_apply(",
    "execute_apply(",
    "rollback_apply(",
    "run_repair_script(",
    "execute_repair(",
)


class TestContinuityKernelPhase6LRuntimeNoSkipEnforcement(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_exists = DOC_PATH.exists()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if cls.doc_exists else ""
        cls.doc_lower = cls.doc_text.lower()

        cls.workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.workflow_lower = cls.workflow_text.lower()

        cls.route_source = ROUTE_PATH.read_text(encoding="utf-8")
        cls.route_lower = cls.route_source.lower()
        cls.route_tree = ast.parse(cls.route_source)

        cls.helper_lower = HELPER_PATH.read_text(encoding="utf-8").lower()

        cls.fastapi_available = find_spec("fastapi") is not None
        cls.httpx_available = find_spec("httpx") is not None

    def _route_method_calls(self, method_name: str) -> list[ast.Call]:
        calls: list[ast.Call] = []
        for node in ast.walk(self.route_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "router" and node.func.attr == method_name:
                    calls.append(node)
        return calls

    def _git_changed_paths(self) -> list[str]:
        candidate_ranges = [
            ["origin/main...HEAD"],
            ["HEAD~1..HEAD"],
        ]
        for diff_range in candidate_ranges:
            try:
                proc = subprocess.run(
                    ["git", "--no-pager", "diff", "--name-only", *diff_range],
                    cwd=REPO_ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except (subprocess.CalledProcessError, FileNotFoundError, OSError):
                continue
            lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
            if lines:
                return lines

        try:
            proc = subprocess.run(
                ["git", "--no-pager", "status", "--porcelain"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            return []

        changed: list[str] = []
        for line in proc.stdout.splitlines():
            if len(line) >= 4:
                changed.append(line[3:].strip())
        return [path for path in changed if path]

    def _run_phase6i_suite(self) -> unittest.TestResult:
        module = import_module(PHASE6I_MODULE)
        suite = unittest.TestLoader().loadTestsFromModule(module)
        return unittest.TextTestRunner(verbosity=0).run(suite)

    def _assert_phase6i_results(self, result: unittest.TestResult, *, enforce_no_skips: bool) -> None:
        if enforce_no_skips:
            self.assertEqual(
                result.skipped,
                [],
                msg=(
                    f"{ENFORCE_NO_SKIP_ENV}=1 requires zero skipped Phase 6I runtime tests; "
                    f"found {len(result.skipped)} skipped tests"
                ),
            )
            self.assertEqual(result.failures, [], msg="Phase 6I failures are not allowed in enforcement mode")
            self.assertEqual(result.errors, [], msg="Phase 6I errors are not allowed in enforcement mode")
            return

        self.assertEqual(result.failures, [], msg="Phase 6I failures are not allowed")
        self.assertEqual(result.errors, [], msg="Phase 6I errors are not allowed")

    def test_01_phase6l_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_skipped_runtime_tests_must_fail_dependency_backed_ci(self) -> None:
        self.assertIn("dependency-backed ci", self.doc_lower)
        self.assertIn("skipped runtime tests must fail the job", self.doc_lower)

    def test_03_doc_includes_runtime_enforcement_env_var(self) -> None:
        self.assertIn(ENFORCE_NO_SKIP_ENV, self.doc_text)

    def test_04_doc_includes_focused_phase6i_runtime_route_command(self) -> None:
        self.assertIn(PHASE6I_FOCUSED_RUNTIME_TEST_COMMAND, self.doc_text)

    def test_05_doc_includes_phase6l_no_skip_command(self) -> None:
        self.assertIn(PHASE6L_NO_SKIP_COMMAND, self.doc_text)

    def test_06_workflow_sets_runtime_no_skip_env_var_for_runtime_job(self) -> None:
        self.assertIn(f"{ENFORCE_NO_SKIP_ENV}: \"1\"", self.workflow_text)

    def test_07_workflow_runs_focused_phase6i_runtime_route_verification_command(self) -> None:
        self.assertIn(PHASE6I_FOCUSED_RUNTIME_TEST_COMMAND, self.workflow_text)

    def test_08_workflow_runs_phase6l_no_skip_command(self) -> None:
        self.assertIn(PHASE6L_NO_SKIP_COMMAND, self.workflow_text)

    def test_09_phase6l_programmatically_runs_or_verifies_phase6i_suite(self) -> None:
        result = self._run_phase6i_suite()
        enforce_no_skips = os.getenv(ENFORCE_NO_SKIP_ENV) == "1"

        if not enforce_no_skips and result.skipped and (not self.fastapi_available or not self.httpx_available):
            missing = []
            if not self.fastapi_available:
                missing.append("fastapi")
            if not self.httpx_available:
                missing.append("httpx")
            self.skipTest(
                "Local/sandbox runtime skip allowed because "
                f"{ENFORCE_NO_SKIP_ENV} is not set and runtime dependency is missing: {', '.join(missing)}"
            )

        self._assert_phase6i_results(result, enforce_no_skips=enforce_no_skips)

    def test_10_enforcement_mode_fails_when_phase6i_results_include_skips(self) -> None:
        synthetic = unittest.TestResult()
        synthetic.addSkip(unittest.FunctionTestCase(lambda: None), "synthetic skip")

        with self.assertRaises(AssertionError):
            self._assert_phase6i_results(synthetic, enforce_no_skips=True)

    def test_11_local_skip_allowed_without_enforcement_when_runtime_dependencies_missing(self) -> None:
        if self.fastapi_available and self.httpx_available:
            self.skipTest("Runtime dependencies are available; local missing-dependency skip case is not applicable")
        if os.getenv(ENFORCE_NO_SKIP_ENV) == "1":
            self.skipTest(f"{ENFORCE_NO_SKIP_ENV}=1 set; local permissive skip case is not applicable")

        result = self._run_phase6i_suite()
        self.assertGreater(len(result.skipped), 0)
        reasons = "\n".join(reason for _, reason in result.skipped).lower()
        self.assertIn("runtime-only test skipped", reasons)
        self.assertIn("missing runtime dependency", reasons)

    def test_12_route_remains_get_only(self) -> None:
        get_calls = self._route_method_calls("get")
        has_preview_get = any(
            call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "/preview"
            for call in get_calls
        )
        self.assertTrue(has_preview_get)

    def test_13_no_post_put_patch_delete_route_was_added(self) -> None:
        self.assertEqual(len(self._route_method_calls("post")), 0)
        self.assertEqual(len(self._route_method_calls("put")), 0)
        self.assertEqual(len(self._route_method_calls("patch")), 0)
        self.assertEqual(len(self._route_method_calls("delete")), 0)

        for path in ROUTES_DIR.glob("**/*.py"):
            if path == ROUTE_PATH:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("/admin/continuity-kernel/preview", text)

    def test_14_no_apply_mode_or_repair_script_was_added(self) -> None:
        self.assertIn("no apply mode", self.doc_lower)
        self.assertIn("no repair scripts", self.doc_lower)

        for token in PROHIBITED_EXEC_TOKENS:
            self.assertNotIn(token, self.route_lower)
            self.assertNotIn(token, self.helper_lower)

        for path in SCRIPTS_PATH.glob("**/*.py"):
            lowered = path.read_text(encoding="utf-8", errors="ignore").lower()
            for token in PROHIBITED_EXEC_TOKENS:
                self.assertNotIn(token, lowered, msg=f"Unexpected token '{token}' in {path}")

    def test_15_no_frontend_files_changed(self) -> None:
        changed_paths = self._git_changed_paths()
        frontend_paths = [path for path in changed_paths if path.startswith("frontend/")]
        self.assertEqual(frontend_paths, [])

    def test_16_no_database_write_calls_were_added(self) -> None:
        self.assertIn("no db writes", self.doc_lower)

        for token in DB_WRITE_TOKENS:
            self.assertNotIn(token, self.route_lower)
            self.assertNotIn(token, self.helper_lower)


if __name__ == "__main__":
    unittest.main()
