import ast
from contextlib import contextmanager
import os
from pathlib import Path
import sys
import unittest
from importlib import import_module


REPO_ROOT = Path(__file__).resolve().parents[3]
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
HELPER_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_readonly_helper.py"
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6i_runtime_route_verification.md"
SCRIPTS_PATH = REPO_ROOT / "backend" / "scripts"
ROUTES_PATH = REPO_ROOT / "backend" / "app" / "routes"
FLAG_NAME = "CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED"

DB_WRITE_TOKENS = (
    "insert_one(",
    "update_one(",
    "update_many(",
    "delete_one(",
    "delete_many(",
    "replace_one(",
    "bulk_write(",
)

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

FORBIDDEN_EXECUTION_MARKERS = (
    "run_repair_script(",
    "execute_repair(",
    "approve_apply(",
    "schedule_apply(",
    "execute_apply(",
    "rollback_apply(",
)


@contextmanager
def _temp_env(updates: dict[str, str | None]):
    original = os.environ.copy()
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)


class TestContinuityKernelPhase6IRuntimeRouteVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.route_source = ROUTE_PATH.read_text(encoding="utf-8")
        cls.route_lower = cls.route_source.lower()
        cls.route_tree = ast.parse(cls.route_source)
        cls.helper_source = HELPER_PATH.read_text(encoding="utf-8")
        cls.helper_lower = cls.helper_source.lower()

        cls.doc_exists = DOC_PATH.exists()
        cls.doc_lower = DOC_PATH.read_text(encoding="utf-8").lower() if cls.doc_exists else ""

        cls.preview_module = import_module("backend.app.core.continuity_kernel_admin_preview")
        cls.helper_module = import_module("backend.app.core.continuity_kernel_readonly_helper")

        cls.runtime_available = False
        cls.runtime_unavailable_reason = ""
        cls.fastapi = None
        cls.testclient_cls = None
        cls.route_module = None
        cls.auth_module = None

        try:
            backend_root = str(REPO_ROOT / "backend")
            if backend_root not in sys.path:
                sys.path.insert(0, backend_root)
            cls.fastapi = import_module("fastapi")
            cls.testclient_cls = import_module("fastapi.testclient").TestClient
            cls.route_module = import_module("app.routes.admin_continuity_preview")
            cls.auth_module = import_module("app.dependencies.auth")
            cls.runtime_available = True
        except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
            missing = getattr(exc, "name", "").strip()
            if missing in {"fastapi", "httpx"}:
                cls.runtime_unavailable_reason = f"Missing runtime dependency: {missing}"
            else:
                raise
        except RuntimeError as exc:  # pragma: no cover - environment dependent
            message = str(exc)
            if "requires the httpx package to be installed" in message.lower():
                cls.runtime_unavailable_reason = "Missing runtime dependency: httpx"
            else:
                raise

    def _helper_response_for_env(self, env: dict | None):
        return self.helper_module.build_readonly_preview_response(
            env=env,
            dry_run_source={"dry_run_id": "admin-readonly-preview", "source": "admin-route", "mode": "read_only"},
            target_selector={"target_type": "workspace", "target_id": "readonly-preview-target"},
            actor_context={"actor_user_id": "a1", "requested_by": "a1", "actor_role": "operations_admin"},
            repair_category="readonly_preview_category",
            before_snapshot={"state": "before"},
            proposed_after_snapshot={"state": "after"},
            diff_summary="read-only admin continuity kernel preview",
            blocked_reasons=[],
            rollback_plan={},
            structured_override=None,
            structured_justification=None,
        )

    def _route_method_calls(self, method_name: str) -> list[ast.Call]:
        calls: list[ast.Call] = []
        for node in ast.walk(self.route_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "router" and node.func.attr == method_name:
                    calls.append(node)
        return calls

    def _require_runtime(self) -> None:
        if not self.runtime_available:
            self.skipTest(f"Runtime-only test skipped: {self.runtime_unavailable_reason}")

    def _runtime_client(self, *, permissions: list[str], role: str = "operations_admin"):
        self._require_runtime()

        app = self.fastapi.FastAPI()
        app.include_router(self.route_module.router)

        def _user_override():
            return {
                "id": "phase6i-admin",
                "email": "admin@example.com",
                "role": role,
                "_access_context": {"permissions": permissions},
            }

        app.dependency_overrides[self.auth_module.get_current_user] = _user_override
        return app, self.testclient_cls(app)

    def test_01_route_file_exists(self) -> None:
        self.assertTrue(ROUTE_PATH.exists())

    def test_02_route_has_get_preview_path(self) -> None:
        get_calls = self._route_method_calls("get")
        self.assertTrue(any(call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "/preview" for call in get_calls))

    def test_03_route_has_no_post_put_patch_delete_definitions(self) -> None:
        self.assertEqual(len(self._route_method_calls("post")), 0)
        self.assertEqual(len(self._route_method_calls("put")), 0)
        self.assertEqual(len(self._route_method_calls("patch")), 0)
        self.assertEqual(len(self._route_method_calls("delete")), 0)

    def test_04_route_uses_existing_admin_permission_guard(self) -> None:
        self.assertIn("from app.dependencies.auth import require_permission", self.route_source)
        self.assertIn('Depends(require_permission("admin.control.view"))', self.route_source)

    def test_05_route_is_feature_flagged_fail_closed(self) -> None:
        self.assertIn("is_enabled = _feature_flag_reader()(env=os.environ)", self.route_source)
        self.assertIn("if not is_enabled:", self.route_source)
        self.assertIn("return build_response(env=os.environ)", self.route_source)

    def test_06_route_does_not_accept_forbidden_approval_inputs(self) -> None:
        forbidden_names = {"approval_fixture_payload", "test_context", "validator_result"}
        target_node = None
        for node in ast.walk(self.route_tree):
            if isinstance(node, ast.FunctionDef) and node.name == "get_admin_preview":
                target_node = node
                break
        self.assertIsNotNone(target_node)
        arg_names = {arg.arg for arg in target_node.args.args}
        self.assertTrue(forbidden_names.isdisjoint(arg_names))

    def test_07_disabled_flag_missing_off_invalid_returns_disabled_without_prohibited_actions(self) -> None:
        self._require_runtime()

        for value in [None, "off", "invalid-value"]:
            with self.subTest(flag=value):
                with _temp_env({FLAG_NAME: value}):
                    response = self.route_module.get_admin_preview(current_user={"id": "a1", "role": "operations_admin"})
                self.assertIs(response.get("enabled"), False)
                self.assertEqual(response.get("status"), "disabled")
                self.assertIsNone(response.get("preview"))
                self.assertTrue(set(response.get("allowed_actions", [])).isdisjoint(PROHIBITED_ACTIONS))

    def test_08_disabled_path_does_not_build_preview_payload(self) -> None:
        self._require_runtime()

        captured: dict = {}

        def _disabled_builder(**kwargs):
            captured.update(kwargs)
            return {
                "enabled": False,
                "status": "disabled",
                "preview": None,
                "validator_result": None,
                "allowed_actions": [],
                "reason_codes": ["FEATURE_FLAG_DISABLED"],
            }

        original_reader = self.route_module._feature_flag_reader
        original_builder = self.route_module._readonly_response_builder
        original_placeholder = self.route_module._placeholder_preview_inputs

        try:
            self.route_module._feature_flag_reader = lambda: (lambda env=None: False)
            self.route_module._readonly_response_builder = lambda: _disabled_builder

            def _should_not_be_called(_current_user):
                raise AssertionError("Disabled branch must not build preview payload")

            self.route_module._placeholder_preview_inputs = _should_not_be_called
            response = self.route_module.get_admin_preview(current_user={"id": "a1", "role": "operations_admin"})
        finally:
            self.route_module._feature_flag_reader = original_reader
            self.route_module._readonly_response_builder = original_builder
            self.route_module._placeholder_preview_inputs = original_placeholder

        self.assertEqual(response.get("status"), "disabled")
        self.assertEqual(set(captured.keys()), {"env"})

    def test_09_enabled_true_like_flag_returns_read_only_envelope_only(self) -> None:
        self._require_runtime()

        with _temp_env({FLAG_NAME: "yes"}):
            response = self.route_module.get_admin_preview(current_user={"id": "a1", "role": "operations_admin"})

        self.assertIs(response.get("enabled"), True)
        self.assertEqual(
            set(response.keys()),
            {"enabled", "status", "preview", "validator_result", "allowed_actions", "reason_codes"},
        )
        self.assertIsInstance(response.get("preview"), dict)

        lowered = str(response).lower()
        self.assertNotIn("rollback_plan", lowered)
        self.assertNotIn("reason_detail", lowered)
        self.assertNotIn("audit_context", lowered)
        self.assertNotIn("approve_apply", lowered)
        self.assertNotIn("schedule_apply", lowered)
        self.assertNotIn("execute_apply", lowered)
        self.assertNotIn("rollback_apply", lowered)
        self.assertNotIn("run_repair_script", lowered)
        self.assertNotIn("execute_repair", lowered)

        prohibited = set(self.preview_module.PROHIBITED_ACTIONS)
        self.assertTrue(set(response.get("allowed_actions", [])).isdisjoint(prohibited))
        self.assertTrue(set(response.get("preview", {}).get("allowed_actions", [])).isdisjoint(prohibited))

    def test_10_non_admin_user_is_denied_at_runtime(self) -> None:
        app, client = self._runtime_client(permissions=[], role="member")
        with _temp_env({FLAG_NAME: "true"}):
            resp = client.get("/admin/continuity-kernel/preview")
        app.dependency_overrides.clear()

        self.assertEqual(resp.status_code, 403)

    def test_11_post_put_patch_delete_methods_are_not_available_at_runtime(self) -> None:
        app, client = self._runtime_client(permissions=["admin.control.view"])
        try:
            with _temp_env({FLAG_NAME: "true"}):
                post = client.post("/admin/continuity-kernel/preview")
                put = client.put("/admin/continuity-kernel/preview")
                patch = client.patch("/admin/continuity-kernel/preview")
                delete = client.delete("/admin/continuity-kernel/preview")
        finally:
            app.dependency_overrides.clear()

        for response in [post, put, patch, delete]:
            self.assertIn(response.status_code, {404, 405})

    def test_12_marketing_admin_or_cmo_get_no_repair_execution_actions(self) -> None:
        self._require_runtime()

        for role in ["marketing_admin", "CMO"]:
            with self.subTest(role=role):
                app, client = self._runtime_client(permissions=["admin.control.view"], role=role)
                try:
                    with _temp_env({FLAG_NAME: "true"}):
                        resp = client.get("/admin/continuity-kernel/preview")
                finally:
                    app.dependency_overrides.clear()

                self.assertEqual(resp.status_code, 200)
                body = resp.json()
                lowered = str(body).lower()
                self.assertNotIn("run_repair_script", lowered)
                self.assertNotIn("execute_repair", lowered)
                self.assertNotIn("approve_apply", lowered)
                self.assertNotIn("schedule_apply", lowered)
                self.assertNotIn("execute_apply", lowered)
                self.assertNotIn("rollback_apply", lowered)
                self.assertTrue(set(body.get("allowed_actions", [])).isdisjoint(PROHIBITED_ACTIONS))

    def test_13_route_does_not_accept_approval_input_query_fields(self) -> None:
        app, client = self._runtime_client(permissions=["admin.control.view"])
        try:
            with _temp_env({FLAG_NAME: "true"}):
                baseline = client.get("/admin/continuity-kernel/preview")
                with_extra = client.get(
                    "/admin/continuity-kernel/preview",
                    params={
                        "approval_fixture_payload": "{\"fake\":true}",
                        "test_context": "true",
                        "validator_result": "{\"passed\":true}",
                    },
                )
        finally:
            app.dependency_overrides.clear()

        self.assertEqual(baseline.status_code, 200)
        self.assertEqual(with_extra.status_code, 200)
        self.assertEqual(with_extra.json(), baseline.json())

    def test_14_no_customer_facing_continuity_kernel_route_exists(self) -> None:
        for path in ROUTES_PATH.glob("**/*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            lowered = text.lower()
            if path == ROUTE_PATH:
                continue
            self.assertNotIn("/continuity-kernel", lowered, msg=f"Unexpected customer-facing continuity-kernel route marker in {path}")

    def test_15_static_guardrails_no_db_writes_no_mint_queue_no_mutation_no_exec_entrypoints(self) -> None:
        for token in DB_WRITE_TOKENS:
            self.assertNotIn(token, self.route_lower)
            self.assertNotIn(token, self.helper_lower)

        for token in ["queue_mint", "mint queue", "mutate_certificate", "customer mutation", "mutate_customer", "mutate_entitlement", "mutate_workspace_member"]:
            self.assertNotIn(token, self.route_lower)
            self.assertNotIn(token, self.helper_lower)

        for token in FORBIDDEN_EXECUTION_MARKERS:
            self.assertNotIn(token, self.route_lower)
            self.assertNotIn(token, self.helper_lower)

        for path in SCRIPTS_PATH.glob("**/*.py"):
            lowered_name = path.name.lower()
            self.assertFalse(("continuity" in lowered_name) and ("repair" in lowered_name))

    def test_16_governance_doc_exists_and_records_runtime_limitations(self) -> None:
        self.assertTrue(self.doc_exists)
        required = [
            "get /admin/continuity-kernel/preview",
            "feature flag",
            "disabled-by-default",
            "admin-only",
            "no mutation",
            "runtime test limitations",
        ]
        for marker in required:
            self.assertIn(marker, self.doc_lower)

    def test_17_helper_enabled_true_like_flag_with_plain_dict_env(self) -> None:
        response = self._helper_response_for_env({FLAG_NAME: "yes"})
        self.assertIs(response.get("enabled"), True)
        self.assertTrue(set(response.get("allowed_actions", [])).isdisjoint(PROHIBITED_ACTIONS))
        self.assertTrue(set(response.get("preview", {}).get("allowed_actions", [])).isdisjoint(PROHIBITED_ACTIONS))

    def test_18_helper_enabled_true_like_flag_with_os_environ_mapping(self) -> None:
        with _temp_env({FLAG_NAME: "yes"}):
            response = self._helper_response_for_env(os.environ)
        self.assertIs(response.get("enabled"), True)
        self.assertTrue(set(response.get("allowed_actions", [])).isdisjoint(PROHIBITED_ACTIONS))
        self.assertTrue(set(response.get("preview", {}).get("allowed_actions", [])).isdisjoint(PROHIBITED_ACTIONS))

    def test_19_helper_missing_off_invalid_flag_still_fail_closed(self) -> None:
        for env in [{}, {FLAG_NAME: "off"}, {FLAG_NAME: "invalid-value"}]:
            with self.subTest(env=env):
                response = self._helper_response_for_env(env)
                self.assertIs(response.get("enabled"), False)
                self.assertEqual(response.get("status"), "disabled")
                self.assertIsNone(response.get("preview"))
                self.assertTrue(set(response.get("allowed_actions", [])).isdisjoint(PROHIBITED_ACTIONS))


if __name__ == "__main__":
    unittest.main()
