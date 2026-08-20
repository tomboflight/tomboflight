import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICE_PATH = REPO_ROOT / "backend" / "app" / "services" / "continuity_runtime_service.py"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_runtime.py"
MAIN_PATH = REPO_ROOT / "backend" / "app" / "main.py"
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase8_operational_runtime.md"
HTML_PATH = REPO_ROOT / "admin-control-center.html"
JS_PATH = REPO_ROOT / "admin-control-center.js"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"


class TestContinuityKernelPhase8OperationalRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.service = SERVICE_PATH.read_text(encoding="utf-8")
        cls.route = ROUTE_PATH.read_text(encoding="utf-8")
        cls.main = MAIN_PATH.read_text(encoding="utf-8")
        cls.doc = DOC_PATH.read_text(encoding="utf-8")
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.js = JS_PATH.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.service_tree = ast.parse(cls.service)
        cls.route_tree = ast.parse(cls.route)

    def test_01_operational_artifacts_exist_and_compile(self) -> None:
        for path in (SERVICE_PATH, ROUTE_PATH, DOC_PATH):
            with self.subTest(path=path):
                self.assertTrue(path.exists())
        self.assertIsNotNone(self.service_tree)
        self.assertIsNotNone(self.route_tree)

    def test_02_runtime_has_persistent_operations_events_and_idempotency_indexes(self) -> None:
        for marker in (
            'OPERATIONS_COLLECTION = "continuity_operations"',
            'EVENTS_COLLECTION = "continuity_events"',
            "continuity_operation_id_unique",
            "continuity_idempotency_unique",
            "continuity_event_id_unique",
        ):
            self.assertIn(marker, self.service)

    def test_03_runtime_exposes_request_approval_execution_failure_and_close_states(self) -> None:
        for state in (
            "review_requested",
            "officer_reviewing",
            "approved_for_apply",
            "apply_scheduled",
            "apply_executed",
            "apply_failed",
            "audit_closed",
        ):
            self.assertIn(state, self.service)
        self.assertIn("validate_apply_request", self.service)
        self.assertIn("SUPERADMIN_EMERGENCY_OVERRIDE", self.service)

    def test_04_execution_is_explicit_and_has_an_emergency_kill_switch(self) -> None:
        self.assertIn("CONTINUITY_EXECUTION_KILL_SWITCH", self.service)
        self.assertIn("def execute_operation", self.service)
        self.assertIn("def execute_governed_action", self.service)
        service_lower = self.service.lower()
        for prohibited_automatic_runtime in ("backgroundtasks", "celery", "apscheduler", "schedule.every"):
            self.assertNotIn(prohibited_automatic_runtime, service_lower)

    def test_05_api_is_authenticated_and_registered_at_startup(self) -> None:
        self.assertIn('prefix="/admin/control-center/kernel"', self.route)
        self.assertIn('Depends(require_permission("admin.control.view"))', self.route)
        self.assertIn("Depends(require_super_admin)", self.route)
        self.assertIn("_assert_canonical_ceo", self.route)
        self.assertIn("app.include_router(admin_continuity_runtime_router)", self.main)
        self.assertIn("ensure_continuity_runtime_indexes()", self.main)

    def test_06_control_center_uses_the_kernel_for_covered_mutations(self) -> None:
        for endpoint in (
            "/admin/control-center/kernel/status",
            "/admin/control-center/kernel/operations",
            "/admin/control-center/kernel/execute",
        ):
            self.assertIn(endpoint, self.js)
        self.assertIn("data-admin-kernel-status", self.html)
        self.assertIn("data-admin-kernel-operations", self.html)
        for legacy_apply_endpoint in (
            "/package-change/apply",
            "/service-controls/apply",
            "/package-revoke/apply",
            "/status-action`",
        ):
            self.assertNotIn(legacy_apply_endpoint, self.js)

    def test_07_partial_domain_failures_are_not_labeled_full_success(self) -> None:
        self.assertIn("def _execution_failure_count", self.service)
        self.assertIn('execution_outcome = "partial_failure"', self.service)
        self.assertIn("EXECUTION_PARTIAL_FAILURE", self.service)
        self.assertIn("partial_failure", self.js)

    def test_08_operational_contract_is_documented_and_dependency_tested(self) -> None:
        for marker in (
            "Operational Runtime",
            "Compatibility boundary",
            "Rollback and failure semantics",
            "CONTINUITY_EXECUTION_KILL_SWITCH",
            "Legacy direct API endpoints remain present",
        ):
            self.assertIn(marker, self.doc)
        self.assertIn("backend.tests.test_continuity_runtime_service", self.workflow)


if __name__ == "__main__":
    unittest.main()
