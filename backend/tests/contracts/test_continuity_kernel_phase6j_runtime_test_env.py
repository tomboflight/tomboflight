import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6j_runtime_test_env.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
HELPER_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_readonly_helper.py"
SCRIPTS_PATH = REPO_ROOT / "backend" / "scripts"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
# Phase 6J validates execution of the existing Phase 6I runtime route verification test.
PHASE6I_FOCUSED_RUNTIME_TEST_COMMAND = "python -m unittest backend.tests.contracts.test_continuity_kernel_phase6i_runtime_route_verification -v"


class TestContinuityKernelPhase6JRuntimeTestEnv(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_exists = DOC_PATH.exists()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if cls.doc_exists else ""
        cls.doc_lower = cls.doc_text.lower()

        cls.route_source = ROUTE_PATH.read_text(encoding="utf-8")
        cls.route_lower = cls.route_source.lower()
        cls.route_tree = ast.parse(cls.route_source)

        cls.helper_source = HELPER_PATH.read_text(encoding="utf-8")
        cls.helper_lower = cls.helper_source.lower()

        cls.workflow_texts: dict[Path, str] = {
            path: path.read_text(encoding="utf-8")
            for path in sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
        }
        cls.runtime_workflows = [
            path for path, text in cls.workflow_texts.items() if PHASE6I_FOCUSED_RUNTIME_TEST_COMMAND in text
        ]

    def _route_method_calls(self, method_name: str) -> list[ast.Call]:
        calls: list[ast.Call] = []
        for node in ast.walk(self.route_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "router" and node.func.attr == method_name:
                    calls.append(node)
        return calls

    def test_01_phase6j_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_runtime_route_tests_require_backend_dependencies(self) -> None:
        self.assertIn("runtime route tests", self.doc_lower)
        self.assertIn("backend dependencies", self.doc_lower)
        self.assertIn("backend/requirements.txt", self.doc_text)

    def test_03_doc_says_no_live_db_required(self) -> None:
        self.assertIn("no live db is required", self.doc_lower)

    def test_04_doc_says_no_live_secrets_required(self) -> None:
        self.assertIn("no live secrets are required", self.doc_lower)

    def test_05_doc_says_no_stripe_web3_calls_required(self) -> None:
        self.assertIn("no stripe/web3 calls are required", self.doc_lower)

    def test_06_doc_says_no_customer_data_required(self) -> None:
        self.assertIn("no customer data is required", self.doc_lower)

    def test_07_doc_includes_focused_route_test_command(self) -> None:
        self.assertIn(PHASE6I_FOCUSED_RUNTIME_TEST_COMMAND, self.doc_text)

    def test_08_runtime_workflow_includes_focused_route_test_command(self) -> None:
        self.assertGreaterEqual(len(self.runtime_workflows), 1)

    def test_09_runtime_workflow_has_no_live_secret_requirements(self) -> None:
        self.assertGreaterEqual(len(self.runtime_workflows), 1)
        forbidden_markers = (
            "secrets.",
            "${{ secrets",
            "aws_access_key_id",
            "aws_secret_access_key",
            "stripe_secret",
            "web3",
        )
        for path in self.runtime_workflows:
            lowered = self.workflow_texts[path].lower()
            for marker in forbidden_markers:
                self.assertNotIn(marker, lowered, msg=f"Unexpected live secret marker '{marker}' in {path}")

    def test_10_runtime_workflow_has_no_mongodb_service_requirement(self) -> None:
        self.assertGreaterEqual(len(self.runtime_workflows), 1)
        for path in self.runtime_workflows:
            lowered = self.workflow_texts[path].lower()
            has_mongodb_service = any(
                marker in lowered
                for marker in ("image: mongo", "image: mongodb", "\n      mongodb:", "\n      mongo:")
            )
            if has_mongodb_service:
                self.assertIn("not needed", lowered)

    def test_11_existing_route_still_get_only(self) -> None:
        self.assertGreaterEqual(len(self._route_method_calls("get")), 1)
        self.assertEqual(len(self._route_method_calls("post")), 0)
        self.assertEqual(len(self._route_method_calls("put")), 0)
        self.assertEqual(len(self._route_method_calls("patch")), 0)
        self.assertEqual(len(self._route_method_calls("delete")), 0)

    def test_12_existing_route_still_feature_flagged(self) -> None:
        self.assertIn("is_enabled = _feature_flag_reader()(env=os.environ)", self.route_source)
        self.assertIn("if not is_enabled:", self.route_source)

    def test_13_existing_route_still_uses_admin_permission_guard(self) -> None:
        self.assertIn('Depends(require_permission("admin.control.view"))', self.route_source)

    def test_14_no_post_put_patch_delete_route_added(self) -> None:
        for path in (REPO_ROOT / "backend" / "app" / "routes").glob("**/*.py"):
            if path == ROUTE_PATH:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("/admin/continuity-kernel/preview", text)

    def test_15_no_apply_mode_or_repair_script_was_added(self) -> None:
        prohibited_tokens = (
            "approve_apply(",
            "schedule_apply(",
            "execute_apply(",
            "rollback_apply(",
            "run_repair_script(",
            "execute_repair(",
        )
        for token in prohibited_tokens:
            self.assertNotIn(token, self.route_lower)
            self.assertNotIn(token, self.helper_lower)

        for path in SCRIPTS_PATH.glob("**/*.py"):
            lowered = path.read_text(encoding="utf-8", errors="ignore").lower()
            for token in prohibited_tokens:
                self.assertNotIn(token, lowered, msg=f"Unexpected token '{token}' in {path}")


if __name__ == "__main__":
    unittest.main()
