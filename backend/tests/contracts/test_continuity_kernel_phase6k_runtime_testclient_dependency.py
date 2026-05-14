import ast
from pathlib import Path
import subprocess
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6k_runtime_testclient_dependency.md"
REQUIREMENTS_PATH = REPO_ROOT / "backend" / "requirements.txt"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
HELPER_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_readonly_helper.py"
SCRIPTS_PATH = REPO_ROOT / "backend" / "scripts"

PHASE6I_FOCUSED_RUNTIME_TEST_COMMAND = "python -m unittest backend.tests.contracts.test_continuity_kernel_phase6i_runtime_route_verification -v"
PROHIBITED_EXEC_TOKENS = (
    "approve_apply(",
    "schedule_apply(",
    "execute_apply(",
    "rollback_apply(",
    "run_repair_script(",
    "execute_repair(",
)


class TestContinuityKernelPhase6KRuntimeTestClientDependency(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_exists = DOC_PATH.exists()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if cls.doc_exists else ""
        cls.doc_lower = cls.doc_text.lower()

        cls.requirements_exists = REQUIREMENTS_PATH.exists()
        cls.requirements_text = REQUIREMENTS_PATH.read_text(encoding="utf-8") if cls.requirements_exists else ""
        cls.requirements_lower = cls.requirements_text.lower()

        cls.workflow_texts: dict[Path, str] = {
            path: path.read_text(encoding="utf-8")
            for path in sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
        }
        cls.runtime_workflows = [
            path for path, text in cls.workflow_texts.items() if PHASE6I_FOCUSED_RUNTIME_TEST_COMMAND in text
        ]

        cls.route_source = ROUTE_PATH.read_text(encoding="utf-8")
        cls.route_lower = cls.route_source.lower()
        cls.route_tree = ast.parse(cls.route_source)
        cls.helper_lower = HELPER_PATH.read_text(encoding="utf-8").lower()

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
            except Exception:
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
        except Exception:
            return []

        changed: list[str] = []
        for line in proc.stdout.splitlines():
            if len(line) >= 4:
                changed.append(line[3:].strip())
        return [path for path in changed if path]

    def test_01_phase6k_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_requirements_include_httpx(self) -> None:
        self.assertTrue(self.requirements_exists)
        self.assertIn("httpx==", self.requirements_lower)

    def test_03_doc_says_httpx_required_for_fastapi_starlette_testclient_runtime_verification(self) -> None:
        self.assertIn("httpx", self.doc_lower)
        self.assertIn("starlette/fastapi testclient runtime verification", self.doc_lower)

    def test_04_doc_says_no_live_db_required(self) -> None:
        self.assertIn("no live db is required", self.doc_lower)

    def test_05_doc_says_no_live_secrets_required(self) -> None:
        self.assertIn("no live secrets are required", self.doc_lower)

    def test_06_doc_says_no_stripe_web3_calls_required(self) -> None:
        self.assertIn("no stripe/web3 calls", self.doc_lower)

    def test_07_doc_says_no_customer_data_required(self) -> None:
        self.assertIn("no customer data", self.doc_lower)

    def test_08_doc_says_no_apply_mode(self) -> None:
        self.assertIn("no apply mode", self.doc_lower)

    def test_09_doc_says_no_repair_scripts(self) -> None:
        self.assertIn("no repair scripts", self.doc_lower)

    def test_10_doc_says_no_db_writes(self) -> None:
        self.assertIn("no db writes", self.doc_lower)

    def test_11_workflow_still_runs_focused_phase6i_route_verification_command(self) -> None:
        self.assertGreaterEqual(len(self.runtime_workflows), 1)

    def test_12_route_remains_get_only(self) -> None:
        get_calls = self._route_method_calls("get")
        self.assertTrue(any(call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "/preview" for call in get_calls))
        self.assertEqual(len(self._route_method_calls("post")), 0)
        self.assertEqual(len(self._route_method_calls("put")), 0)
        self.assertEqual(len(self._route_method_calls("patch")), 0)
        self.assertEqual(len(self._route_method_calls("delete")), 0)

    def test_13_no_post_put_patch_delete_route_was_added(self) -> None:
        for path in ROUTES_DIR.glob("**/*.py"):
            if path == ROUTE_PATH:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("/admin/continuity-kernel/preview", text)

    def test_14_no_apply_mode_or_repair_script_was_added(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
