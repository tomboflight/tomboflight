from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6g_readonly_route_design.md"


class TestContinuityKernelPhase6GReadonlyRouteDesign(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_exists = DOC_PATH.exists()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if cls.doc_exists else ""
        cls.doc_lower = cls.doc_text.lower()

    def _assert_no_kernel_token_in_paths(self, paths: list[Path]) -> None:
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            self.assertNotIn("continuity_kernel_", text, msg=f"Unexpected Continuity Kernel token in {path}")

    def test_01_phase6g_route_design_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_includes_canonical_future_route_path(self) -> None:
        self.assertIn("get /admin/continuity-kernel/preview", self.doc_lower)

    def test_03_doc_says_route_is_get_only(self) -> None:
        self.assertIn("get only", self.doc_lower)

    def test_04_doc_says_route_is_admin_only(self) -> None:
        self.assertIn("admin-only", self.doc_lower)

    def test_05_doc_says_route_is_read_only(self) -> None:
        self.assertIn("read-only", self.doc_lower)

    def test_06_doc_says_route_is_feature_flagged(self) -> None:
        self.assertIn("feature-flagged", self.doc_lower)

    def test_07_doc_says_route_is_disabled_by_default(self) -> None:
        self.assertIn("disabled by default", self.doc_lower)

    def test_08_doc_says_no_customer_facing_exposure(self) -> None:
        self.assertIn("no customer-facing exposure", self.doc_lower)

    def test_09_doc_requires_authenticated_admin(self) -> None:
        self.assertIn("authenticated admin required", self.doc_lower)

    def test_10_doc_requires_officer_role(self) -> None:
        self.assertIn("officer role required", self.doc_lower)

    def test_11_doc_says_feature_flag_off_missing_invalid_returns_disabled(self) -> None:
        self.assertIn("if continuity_kernel_readonly_admin_preview_enabled is missing/off/invalid, route returns disabled response", self.doc_lower)

    def test_12_doc_says_no_preview_payload_built_when_flag_off(self) -> None:
        self.assertIn("no preview payload built when flag is off", self.doc_lower)

    def test_13_doc_says_no_prohibited_actions_when_flag_off(self) -> None:
        self.assertIn("no prohibited actions returned when flag is off", self.doc_lower)

    def test_14_doc_says_response_is_read_only_preview_envelope_only(self) -> None:
        self.assertIn("read-only preview envelope only", self.doc_lower)

    def test_15_doc_says_no_apply_schedule_execute_rollback_actions(self) -> None:
        self.assertIn("no apply/schedule/execute/rollback actions", self.doc_lower)

    def test_16_doc_says_no_db_writes(self) -> None:
        self.assertIn("no db writes", self.doc_lower)

    def test_17_doc_says_no_mint_queueing(self) -> None:
        self.assertIn("no mint queueing", self.doc_lower)

    def test_18_doc_says_no_certificate_customer_mutation(self) -> None:
        self.assertIn("no certificate/customer mutation", self.doc_lower)

    def test_19_doc_says_no_full_rollback_plan(self) -> None:
        self.assertIn("no full rollback_plan", self.doc_lower)

    def test_20_doc_says_no_full_override_justification_reason_detail(self) -> None:
        self.assertIn("no full override reason_detail", self.doc_lower)
        self.assertIn("no full justification reason_detail", self.doc_lower)

    def test_21_doc_says_no_full_audit_context(self) -> None:
        self.assertIn("no full audit_context", self.doc_lower)

    def test_22_doc_forbids_post_put_patch_delete(self) -> None:
        self.assertIn("post/put/patch/delete", self.doc_lower)

    def test_23_doc_forbids_accepting_validator_result_as_user_approval_input(self) -> None:
        self.assertIn("accepting validator_result as user approval input", self.doc_lower)

    def test_24_doc_forbids_accepting_approval_fixture_payload_from_request_user_input(self) -> None:
        self.assertIn("accepting approval_fixture_payload from request/user input", self.doc_lower)

    def test_25_doc_forbids_accepting_test_context_from_request_user_input(self) -> None:
        self.assertIn("accepting test_context from request/user input", self.doc_lower)

    def test_26_doc_includes_all_required_future_route_tests(self) -> None:
        required = [
            "flag off returns disabled",
            "flag missing returns disabled",
            "flag invalid returns disabled",
            "non-admin denied",
            "marketing_admin denied or receives no actions",
            "response contains no prohibited actions",
            "no db writes called",
            "no apply/schedule/execute/rollback route exists",
            "no post/put/patch/delete route exists",
            "no fixture/test_context request path exists",
            "no customer-facing route exists",
        ]
        for value in required:
            self.assertIn(value, self.doc_lower)

    def test_27_existing_routes_do_not_import_continuity_kernel_modules_yet(self) -> None:
        routes_paths = list((REPO_ROOT / "backend" / "app" / "routes").glob("**/*.py"))
        self._assert_no_kernel_token_in_paths(routes_paths)

    def test_28_existing_services_do_not_import_continuity_kernel_modules_yet(self) -> None:
        services_paths = list((REPO_ROOT / "backend" / "app" / "services").glob("**/*.py"))
        self._assert_no_kernel_token_in_paths(services_paths)

    def test_29_existing_scripts_do_not_import_continuity_kernel_modules_yet(self) -> None:
        scripts_paths = list((REPO_ROOT / "backend" / "scripts").glob("**/*.py"))
        self._assert_no_kernel_token_in_paths(scripts_paths)

    def test_30_main_does_not_import_continuity_kernel_modules_yet(self) -> None:
        main_path = REPO_ROOT / "backend" / "app" / "main.py"
        self._assert_no_kernel_token_in_paths([main_path])


if __name__ == "__main__":
    unittest.main()
