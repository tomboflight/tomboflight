import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6z_staging_governance_closeout.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"
EXECUTABLE_PERMISSION_BITS = 0o111

PHASE6_SYSTEM_ARTIFACTS = [
    "Phase 6A feature flag scaffold",
    "Phase 6B feature flag helper",
    "Phase 6C isolated read-only helper",
    "Phase 6D staging payload alignment",
    "Phase 6E valid in-memory approval fixtures",
    "Phase 6F test-fixture guardrails",
    "Phase 6G read-only route design",
    "Phase 6H read-only admin route",
    "Phase 6I runtime route verification",
    "Phase 6J runtime test environment",
    "Phase 6K TestClient dependency enforcement",
    "Phase 6L runtime no-skip enforcement",
    "Phase 6M post-merge runtime certification",
]

PHASE6_STAGING_GOVERNANCE_ARTIFACTS = [
    "Phase 6N staging readiness review",
    "Phase 6O staging flag runbook",
    "Phase 6P staging approval evidence package",
    "Phase 6Q staging execution result record",
    "Phase 6R staging approval packet index",
    "Phase 6S staging go/no-go certification",
    "Phase 6T post-6S readiness lock",
    "Phase 6U staging manual test packet",
    "Phase 6V staging preflight evidence refresh",
    "Phase 6W staging manual test command checklist",
    "Phase 6X staging execution approval summary",
    "Phase 6Y final staging packet closeout index",
]

CERTIFIED_CURRENT_ROUTE_STATE = [
    "GET /admin/continuity-kernel/preview exists",
    "route is admin-only",
    "route is feature-flagged",
    "route is disabled by default",
    "route is GET-only",
    "no POST/PUT/PATCH/DELETE route exists",
    "no customer-facing route exists",
    "no prohibited actions are returned",
    "dependency-backed CI has focused Phase 6I zero runtime skips",
    "Phase 6L no-skip enforcement exists",
]

CERTIFIED_PROHIBITIONS = [
    "no production flag enablement",
    "no apply mode",
    "no repair execution",
    "no executable repair scripts",
    "no database writes",
    "no mint queueing",
    "no certificate/customer mutation",
    "no frontend/admin button exposure",
    "no customer-facing exposure",
]

REQUIRED_BEFORE_MANUAL_STAGING = [
    "owner/CEO approval",
    "technical reviewer approval",
    "rollback owner",
    "QA owner",
    "monitoring owner",
    "production flag confirmed off",
    "dependency-backed CI zero-skip proof",
    "Phase 6S go decision",
    "Phase 6X approval summary completed",
    "Phase 6W command checklist ready",
    "Phase 6Q execution record ready",
]

PHASE6A_TO_PHASE6Y_DOC_PATHS = [
    "backend/docs/governance/continuity_kernel_phase6a_feature_flag_scaffold.md",
    "backend/docs/governance/continuity_kernel_phase6b_feature_flag_module.md",
    "backend/docs/governance/continuity_kernel_phase6c_isolated_readonly_helper.md",
    "backend/docs/governance/continuity_kernel_phase6d_staging_payload_alignment.md",
    "backend/docs/governance/continuity_kernel_phase6e_valid_approval_fixtures.md",
    "backend/docs/governance/continuity_kernel_phase6f_test_fixture_guardrails.md",
    "backend/docs/governance/continuity_kernel_phase6g_readonly_route_design.md",
    "backend/docs/governance/continuity_kernel_phase6h_readonly_admin_route.md",
    "backend/docs/governance/continuity_kernel_phase6i_runtime_route_verification.md",
    "backend/docs/governance/continuity_kernel_phase6j_runtime_test_env.md",
    "backend/docs/governance/continuity_kernel_phase6k_runtime_testclient_dependency.md",
    "backend/docs/governance/continuity_kernel_phase6l_runtime_no_skip_enforcement.md",
    "backend/docs/governance/continuity_kernel_phase6m_postmerge_runtime_certification.md",
    "backend/docs/governance/continuity_kernel_phase6n_staging_preview_readiness.md",
    "backend/docs/governance/continuity_kernel_phase6o_staging_flag_runbook.md",
    "backend/docs/governance/continuity_kernel_phase6p_staging_approval_evidence.md",
    "backend/docs/governance/continuity_kernel_phase6q_staging_execution_record.md",
    "backend/docs/governance/continuity_kernel_phase6r_staging_approval_packet_index.md",
    "backend/docs/governance/continuity_kernel_phase6s_staging_go_no_go_certification.md",
    "backend/docs/governance/continuity_kernel_phase6t_post_6s_readiness_lock.md",
    "backend/docs/governance/continuity_kernel_phase6u_staging_manual_test_packet.md",
    "backend/docs/governance/continuity_kernel_phase6v_staging_preflight_evidence.md",
    "backend/docs/governance/continuity_kernel_phase6w_staging_test_command_checklist.md",
    "backend/docs/governance/continuity_kernel_phase6x_staging_execution_approval_summary.md",
    "backend/docs/governance/continuity_kernel_phase6y_final_staging_packet_closeout.md",
]


class TestContinuityKernelPhase6ZStagingGovernanceCloseout(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_exists = DOC_PATH.exists()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if cls.doc_exists else ""
        cls.doc_lower = cls.doc_text.lower()

        cls.route_source = ROUTE_PATH.read_text(encoding="utf-8")
        cls.route_tree = ast.parse(cls.route_source)

        cls.workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    def _route_method_calls(self, method_name: str) -> list[ast.Call]:
        calls: list[ast.Call] = []
        for node in ast.walk(self.route_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "router" and node.func.attr == method_name:
                    calls.append(node)
        return calls

    def test_01_phase6z_closeout_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_final_phase6_staging_governance_closeout_certification(self) -> None:
        self.assertIn("final phase 6 staging governance closeout certification", self.doc_lower)

    def test_03_doc_says_staging_only_preparation_is_complete(self) -> None:
        self.assertIn("staging-only preparation is complete", self.doc_lower)

    def test_04_doc_says_only_remaining_action_is_an_approved_manual_staging_flag_test(self) -> None:
        self.assertIn("only remaining action is an approved manual staging flag test", self.doc_lower)

    def test_05_doc_says_no_production_enablement(self) -> None:
        self.assertIn("no production enablement", self.doc_lower)

    def test_06_doc_says_no_apply_mode(self) -> None:
        self.assertIn("no apply mode", self.doc_lower)

    def test_07_doc_says_no_repair_execution(self) -> None:
        self.assertIn("no repair execution", self.doc_lower)

    def test_08_doc_says_no_data_mutation(self) -> None:
        self.assertIn("no data mutation", self.doc_lower)

    def test_09_doc_includes_all_completed_phase6_system_artifacts(self) -> None:
        for marker in PHASE6_SYSTEM_ARTIFACTS:
            self.assertIn(marker, self.doc_text)

    def test_10_doc_includes_all_completed_phase6_staging_governance_artifacts(self) -> None:
        for marker in PHASE6_STAGING_GOVERNANCE_ARTIFACTS:
            self.assertIn(marker, self.doc_text)

    def test_11_doc_includes_all_certified_current_route_state_items(self) -> None:
        for marker in CERTIFIED_CURRENT_ROUTE_STATE:
            self.assertIn(marker, self.doc_text)

    def test_12_doc_includes_all_certified_prohibitions(self) -> None:
        for marker in CERTIFIED_PROHIBITIONS:
            self.assertIn(marker, self.doc_text)

    def test_13_doc_includes_all_required_before_manual_staging_items(self) -> None:
        for marker in REQUIRED_BEFORE_MANUAL_STAGING:
            self.assertIn(marker, self.doc_text)

    def test_14_doc_says_phase6_staging_governance_is_complete(self) -> None:
        self.assertIn("phase 6 staging governance is complete", self.doc_lower)

    def test_15_doc_says_phase6z_does_not_itself_authorize_production(self) -> None:
        self.assertIn("phase 6z does not itself authorize production", self.doc_lower)

    def test_16_doc_says_phase6z_does_not_itself_enable_staging(self) -> None:
        self.assertIn("phase 6z does not itself enable staging", self.doc_lower)

    def test_17_doc_says_manual_staging_test_may_proceed_only_after_required_approvals_are_completed(self) -> None:
        self.assertIn("manual staging test may proceed only after required approvals are completed", self.doc_lower)

    def test_18_doc_says_phase6z_does_not_enable_the_flag(self) -> None:
        self.assertIn("phase 6z does not enable the flag", self.doc_lower)

    def test_19_doc_says_phase6z_does_not_change_render_settings(self) -> None:
        self.assertIn("phase 6z does not change render settings", self.doc_lower)

    def test_20_doc_says_phase6z_does_not_change_production_settings(self) -> None:
        self.assertIn("phase 6z does not change production settings", self.doc_lower)

    def test_21_doc_says_phase6z_does_not_create_apply_mode_or_repair_scripts(self) -> None:
        self.assertIn("phase 6z does not create apply mode or repair scripts", self.doc_lower)

    def test_22_doc_says_phase6z_does_not_touch_live_data(self) -> None:
        self.assertIn("phase 6z does not touch live data", self.doc_lower)

    def test_23_phase6a_through_phase6y_docs_exist_where_applicable(self) -> None:
        for relative_path in PHASE6A_TO_PHASE6Y_DOC_PATHS:
            self.assertTrue((REPO_ROOT / relative_path).exists(), msg=f"Missing Phase 6 artifact doc: {relative_path}")

    def test_24_route_remains_get_only(self) -> None:
        get_calls = self._route_method_calls("get")
        has_preview_get = any(
            call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "/preview"
            for call in get_calls
        )
        self.assertTrue(has_preview_get)

    def test_25_no_post_put_patch_delete_route_exists(self) -> None:
        self.assertEqual(len(self._route_method_calls("post")), 0)
        self.assertEqual(len(self._route_method_calls("put")), 0)
        self.assertEqual(len(self._route_method_calls("patch")), 0)
        self.assertEqual(len(self._route_method_calls("delete")), 0)

        for path in ROUTES_DIR.glob("**/*.py"):
            if path == ROUTE_PATH:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("/admin/continuity-kernel/preview", text)

    def test_26_workflow_still_enforces_no_skips(self) -> None:
        self.assertIn('CONTINUITY_KERNEL_RUNTIME_TEST_ENFORCE_NO_SKIPS: "1"', self.workflow_text)
        self.assertIn(
            "python -m unittest backend.tests.contracts.test_continuity_kernel_phase6l_runtime_no_skip_enforcement -v",
            self.workflow_text,
        )

    def test_27_no_executable_repair_script_exists(self) -> None:
        repair_named_files = [path for path in SCRIPTS_DIR.glob("**/*") if path.is_file() and "repair" in path.name.lower()]
        self.assertEqual(len(repair_named_files), 0, msg=f"Found unexpected repair-named files: {repair_named_files}")

        for path in SCRIPTS_DIR.glob("**/*.py"):
            self.assertFalse(
                path.stat().st_mode & EXECUTABLE_PERMISSION_BITS,
                msg=f"Unexpected executable script bit set: {path}",
            )


if __name__ == "__main__":
    unittest.main()
