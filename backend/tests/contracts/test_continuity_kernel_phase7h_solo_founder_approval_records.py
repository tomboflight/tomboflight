import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
RECORDS_DIR = REPO_ROOT / "backend" / "docs" / "governance" / "records"
PHASE7C_PATH = RECORDS_DIR / "continuity_kernel_phase7c_approval_record_CK-7C-001.md"
PHASE7D_PATH = RECORDS_DIR / "continuity_kernel_phase7d_completion_checklist_CK-7D-001.md"
PHASE7E_PATH = RECORDS_DIR / "continuity_kernel_phase7e_authorization_certificate_CK-7E-001.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"
EXECUTABLE_PERMISSION_BITS = 0o111


class TestContinuityKernelPhase7HSoloFounderApprovalRecords(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.phase7c_exists = PHASE7C_PATH.exists()
        cls.phase7d_exists = PHASE7D_PATH.exists()
        cls.phase7e_exists = PHASE7E_PATH.exists()

        cls.phase7c_text = PHASE7C_PATH.read_text(encoding="utf-8") if cls.phase7c_exists else ""
        cls.phase7d_text = PHASE7D_PATH.read_text(encoding="utf-8") if cls.phase7d_exists else ""
        cls.phase7e_text = PHASE7E_PATH.read_text(encoding="utf-8") if cls.phase7e_exists else ""

        cls.phase7c_lower = cls.phase7c_text.lower()
        cls.phase7d_lower = cls.phase7d_text.lower()
        cls.phase7e_lower = cls.phase7e_text.lower()

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

    def test_01_records_directory_exists(self) -> None:
        self.assertTrue(RECORDS_DIR.exists())

    def test_02_phase7c_record_exists(self) -> None:
        self.assertTrue(self.phase7c_exists)

    def test_03_phase7d_checklist_exists(self) -> None:
        self.assertTrue(self.phase7d_exists)

    def test_04_phase7e_certificate_exists(self) -> None:
        self.assertTrue(self.phase7e_exists)

    def test_05_phase7c_says_solo_founder_owner_operated(self) -> None:
        self.assertIn("governance_posture: solo_founder_owner_operated", self.phase7c_text)

    def test_06_phase7d_says_solo_founder_owner_operated(self) -> None:
        self.assertIn("governance_posture: solo_founder_owner_operated", self.phase7d_text)

    def test_07_phase7e_says_solo_founder_owner_operated(self) -> None:
        self.assertIn("governance_posture: solo_founder_owner_operated", self.phase7e_text)

    def test_08_phase7c_includes_larry_robinson_as_owner_ceo(self) -> None:
        self.assertIn("owner_ceo_name: Larry Robinson", self.phase7c_text)

    def test_09_phase7c_includes_larry_robinson_as_acting_technical_reviewer(self) -> None:
        self.assertIn("technical_reviewer_name: Larry Robinson, acting technical reviewer", self.phase7c_text)

    def test_10_phase7c_includes_larry_robinson_in_all_owner_roles(self) -> None:
        for marker in [
            "qa_owner_name: Larry Robinson",
            "monitoring_owner_name: Larry Robinson",
            "rollback_owner_name: Larry Robinson",
            "staging_operator_name: Larry Robinson",
        ]:
            self.assertIn(marker, self.phase7c_text)

    def test_11_phase7c_says_not_ready_until_test_window_and_final_flag_off_confirmation(self) -> None:
        self.assertIn(
            "final_readiness_decision: not_ready_until_test_window_and_final_flag_off_confirmation",
            self.phase7c_text,
        )

    def test_12_phase7d_says_not_ready_until_test_window_and_final_flag_off_confirmation(self) -> None:
        self.assertIn("completion_decision: not_ready_until_test_window_and_final_flag_off_confirmation", self.phase7d_text)

    def test_13_phase7e_says_not_authorized_until_test_window_and_final_flag_off_confirmation(self) -> None:
        self.assertIn(
            "authorization_decision: not_authorized_until_test_window_and_final_flag_off_confirmation",
            self.phase7e_text,
        )

    def test_14_phase7e_final_authorization_decision_line_is_not_authorized(self) -> None:
        self.assertIn(
            "## 7. Final authorization decision\n\n- authorization_decision: not_authorized_until_test_window_and_final_flag_off_confirmation",
            self.phase7e_text,
        )
        self.assertNotIn("- authorization_decision: authorized_for_manual_staging_test", self.phase7e_text)

    def test_15_all_records_say_they_do_not_enable_the_flag(self) -> None:
        self.assertIn("this record does not enable the flag.", self.phase7c_lower)
        self.assertIn("this checklist does not enable the flag.", self.phase7d_lower)
        self.assertIn("this certificate does not enable the flag.", self.phase7e_lower)

    def test_16_all_records_say_they_do_not_change_render_settings(self) -> None:
        self.assertIn("this record does not change render settings.", self.phase7c_lower)
        self.assertIn("this checklist does not change render settings.", self.phase7d_lower)
        self.assertIn("this certificate does not change render settings.", self.phase7e_lower)

    def test_17_all_records_say_they_do_not_change_production_settings(self) -> None:
        self.assertIn("this record does not change production settings.", self.phase7c_lower)
        self.assertIn("this checklist does not change production settings.", self.phase7d_lower)
        self.assertIn("this certificate does not change production settings.", self.phase7e_lower)

    def test_18_all_records_say_they_do_not_create_apply_mode(self) -> None:
        self.assertIn("this record does not create apply mode.", self.phase7c_lower)
        self.assertIn("this checklist does not create apply mode.", self.phase7d_lower)
        self.assertIn("this certificate does not create apply mode.", self.phase7e_lower)

    def test_19_all_records_say_they_do_not_create_repair_scripts(self) -> None:
        self.assertIn("this record does not create repair scripts.", self.phase7c_lower)
        self.assertIn("this checklist does not create repair scripts.", self.phase7d_lower)
        self.assertIn("this certificate does not create repair scripts.", self.phase7e_lower)

    def test_20_all_records_say_they_do_not_touch_live_data(self) -> None:
        self.assertIn("this record does not touch live data.", self.phase7c_lower)
        self.assertIn("this checklist does not touch live data.", self.phase7d_lower)
        self.assertIn("this certificate does not touch live data.", self.phase7e_lower)

    def test_21_route_remains_get_only(self) -> None:
        get_calls = self._route_method_calls("get")
        has_preview_get = any(
            call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "/preview"
            for call in get_calls
        )
        self.assertTrue(has_preview_get)

    def test_22_no_post_put_patch_delete_route_exists(self) -> None:
        self.assertEqual(len(self._route_method_calls("post")), 0)
        self.assertEqual(len(self._route_method_calls("put")), 0)
        self.assertEqual(len(self._route_method_calls("patch")), 0)
        self.assertEqual(len(self._route_method_calls("delete")), 0)

        for path in ROUTES_DIR.glob("**/*.py"):
            if path == ROUTE_PATH:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertNotIn("/admin/continuity-kernel/preview", text)

    def test_23_workflow_still_enforces_no_skips(self) -> None:
        self.assertIn('CONTINUITY_KERNEL_RUNTIME_TEST_ENFORCE_NO_SKIPS: "1"', self.workflow_text)
        self.assertIn(
            "python -m unittest backend.tests.contracts.test_continuity_kernel_phase6l_runtime_no_skip_enforcement -v",
            self.workflow_text,
        )

    def test_24_no_executable_repair_script_exists(self) -> None:
        repair_named_files = [path for path in SCRIPTS_DIR.glob("**/*") if path.is_file() and "repair" in path.name.lower()]
        self.assertEqual(repair_named_files, [])

        for path in SCRIPTS_DIR.glob("**/*.py"):
            self.assertFalse(
                path.stat().st_mode & EXECUTABLE_PERMISSION_BITS,
                msg=f"Unexpected executable script bit set: {path}",
            )


if __name__ == "__main__":
    unittest.main()
