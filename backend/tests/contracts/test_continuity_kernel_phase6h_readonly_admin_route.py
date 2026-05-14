import ast
from importlib import import_module
import os
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
MAIN_PATH = REPO_ROOT / "backend" / "app" / "main.py"
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6h_readonly_admin_route.md"
FRONTEND_PATH = REPO_ROOT / "frontend"
SCRIPTS_PATH = REPO_ROOT / "backend" / "scripts"

PROHIBITED_ACTIONS = {
    "approve_apply",
    "schedule_apply",
    "execute_apply",
    "rollback_apply",
    "mutate_entitlement",
    "mutate_workspace_member",
    "mutate_certificate",
    "queue_mint",
    "delete_customer_record",
    "bypass_validator",
    "bypass_audit",
}

DB_WRITE_TOKENS = (
    "insert_one(",
    "update_one(",
    "update_many(",
    "delete_one(",
    "delete_many(",
    "replace_one(",
    "bulk_write(",
)

EXECUTION_TOKENS = (
    "approve_apply(",
    "schedule_apply(",
    "execute_apply(",
    "rollback_apply(",
    "run_repair_script(",
    "execute_repair(",
)


class TestContinuityKernelPhase6HReadonlyAdminRoute(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.route_exists = ROUTE_PATH.exists()
        cls.route_source = ROUTE_PATH.read_text(encoding="utf-8") if cls.route_exists else ""
        cls.route_lower = cls.route_source.lower()
        cls.route_tree = ast.parse(cls.route_source) if cls.route_exists else None
        cls.main_source = MAIN_PATH.read_text(encoding="utf-8")
        cls.main_lower = cls.main_source.lower()
        cls.doc_exists = DOC_PATH.exists()
        cls.doc_lower = DOC_PATH.read_text(encoding="utf-8").lower() if cls.doc_exists else ""
        cls.route_module = None
        cls.route_import_error = None
        if cls.route_exists:
            try:
                cls.route_module = import_module("backend.app.routes.admin_continuity_preview")
            except ModuleNotFoundError as exc:
                cls.route_import_error = str(exc)
        cls.preview_module = import_module("backend.app.core.continuity_kernel_admin_preview")

    def _decorator_calls(self, function_name: str) -> list[ast.Call]:
        calls: list[ast.Call] = []
        for node in ast.walk(self.route_tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        calls.append(decorator)
        return calls

    def _route_method_calls(self, method_name: str) -> list[ast.Call]:
        calls: list[ast.Call] = []
        for node in ast.walk(self.route_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "router" and node.func.attr == method_name:
                    calls.append(node)
        return calls

    def _with_env(self, env_updates: dict | None):
        class _EnvGuard:
            def __enter__(self_nonlocal):
                self_nonlocal._original = os.environ.copy()
                os.environ.clear()
                os.environ.update(self_nonlocal._original)
                if env_updates is not None:
                    for key, value in env_updates.items():
                        if value is None:
                            os.environ.pop(key, None)
                        else:
                            os.environ[key] = value
                return self_nonlocal

            def __exit__(self_nonlocal, exc_type, exc, tb):
                os.environ.clear()
                os.environ.update(self_nonlocal._original)

        return _EnvGuard()

    def test_01_route_file_exists(self) -> None:
        self.assertTrue(self.route_exists)

    def test_02_main_imports_and_includes_route_router(self) -> None:
        self.assertIn("from app.routes.admin_continuity_preview import router as admin_continuity_preview_router", self.main_source)
        self.assertIn("app.include_router(admin_continuity_preview_router)", self.main_source)

    def test_03_route_uses_admin_auth_dependency(self) -> None:
        self.assertIn('require_permission("admin.control.view")', self.route_source)

    def test_04_route_has_get_preview_path(self) -> None:
        get_calls = self._route_method_calls("get")
        self.assertTrue(any(call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "/preview" for call in get_calls))

    def test_05_route_has_no_post_put_patch_delete(self) -> None:
        self.assertEqual(len(self._route_method_calls("post")), 0)
        self.assertEqual(len(self._route_method_calls("put")), 0)
        self.assertEqual(len(self._route_method_calls("patch")), 0)
        self.assertEqual(len(self._route_method_calls("delete")), 0)

    def test_06_route_does_not_accept_forbidden_request_inputs(self) -> None:
        forbidden_names = {"approval_fixture_payload", "test_context", "validator_result"}
        for node in ast.walk(self.route_tree):
            if isinstance(node, ast.FunctionDef) and node.name == "get_admin_preview":
                arg_names = {arg.arg for arg in node.args.args}
                self.assertTrue(forbidden_names.isdisjoint(arg_names))

    def test_07_route_source_uses_feature_flag_reader_and_fail_closed_disabled_branch(self) -> None:
        self.assertIn("is_enabled = _feature_flag_reader()(env=os.environ)", self.route_source)
        self.assertIn("if not is_enabled:", self.route_source)
        self.assertIn("return build_response(env=os.environ)", self.route_source)

    def test_08_route_source_only_builds_placeholder_inputs_on_enabled_branch(self) -> None:
        self.assertIn("**_placeholder_preview_inputs(current_user)", self.route_source)
        disabled_idx = self.route_source.index("return build_response(env=os.environ)")
        enabled_idx = self.route_source.index("**_placeholder_preview_inputs(current_user)")
        self.assertLess(disabled_idx, enabled_idx)

    def test_09_runtime_flag_behavior_when_fastapi_is_available(self) -> None:
        if self.route_module is None:
            self.skipTest(f"Runtime route import unavailable in this environment: {self.route_import_error}")
        with self._with_env({"CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED": "off"}):
            response = self.route_module.get_admin_preview(current_user={"id": "admin-1"})
        self.assertEqual(response.get("status"), "disabled")
        self.assertIs(response.get("enabled"), False)
        self.assertIsNone(response.get("preview"))
        self.assertTrue(set(response.get("allowed_actions", [])).isdisjoint(PROHIBITED_ACTIONS))

    def test_10_runtime_enabled_shape_when_fastapi_is_available(self) -> None:
        if self.route_module is None:
            self.skipTest(f"Runtime route import unavailable in this environment: {self.route_import_error}")
        with self._with_env({"CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED": "true"}):
            response = self.route_module.get_admin_preview(current_user={"id": "admin-1", "role": "operations_admin"})
        self.assertIs(response.get("enabled"), True)
        self.assertIn("status", response)
        self.assertIsInstance(response.get("preview"), dict)
        serialized = str(response).lower()
        self.assertNotIn("rollback_plan", serialized)
        self.assertNotIn("reason_detail", serialized)
        self.assertNotIn("audit_context", serialized)

    def test_11_route_and_helper_files_contain_no_database_write_tokens(self) -> None:
        helper_path = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_readonly_helper.py"
        helper_lower = helper_path.read_text(encoding="utf-8").lower()
        for token in DB_WRITE_TOKENS:
            self.assertNotIn(token, self.route_lower)
            self.assertNotIn(token, helper_lower)

    def test_12_route_contains_no_apply_schedule_execute_rollback_behavior(self) -> None:
        for token in EXECUTION_TOKENS:
            self.assertNotIn(token, self.route_lower)

    def test_13_no_continuity_kernel_repair_scripts_exist_under_backend_scripts(self) -> None:
        for path in SCRIPTS_PATH.glob("**/*.py"):
            lowered_name = path.name.lower()
            self.assertFalse("continuity" in lowered_name and "repair" in lowered_name)

    def test_14_frontend_has_no_continuity_kernel_admin_preview_file(self) -> None:
        for path in FRONTEND_PATH.glob("**/*"):
            lowered = path.name.lower()
            self.assertFalse("continuity-kernel" in lowered and "preview" in lowered and path.is_file())

    def test_15_doc_exists_and_states_safety_constraints(self) -> None:
        self.assertTrue(self.doc_exists)
        required = [
            "get /admin/continuity-kernel/preview",
            "get-only",
            "admin-only",
            "feature flag",
            "disabled-by-default",
            "no apply mode",
            "no repair execution",
            "no db writes",
            "no mint queueing",
            "no certificate/customer mutation",
            "no customer-facing exposure",
            "no prohibited actions",
            "disable feature flag",
            "remove route pr if needed",
            "verify no data was mutated",
            "run architecture and contract tests",
        ]
        for item in required:
            self.assertIn(item, self.doc_lower)


if __name__ == "__main__":
    unittest.main()
