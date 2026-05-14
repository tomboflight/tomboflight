from copy import deepcopy
from importlib import import_module
from pathlib import Path
import ast
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_admin_preview.py"
MODULE_IMPORT = "backend.app.core.continuity_kernel_admin_preview"


class TestContinuityKernelPhase5LAdminPreviewModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module_exists = MODULE_PATH.exists()
        cls.source_text = MODULE_PATH.read_text(encoding="utf-8") if cls.module_exists else ""
        cls.source_lower = cls.source_text.lower()
        cls.module = import_module(MODULE_IMPORT) if cls.module_exists else None

    def _base_payload(self) -> dict:
        return {
            "evidence_packet": {
                "target_type": "workspace",
                "target_id": "ws-001",
                "repair_category": "workspace_upload_readiness_preview",
                "risk_level": "high",
                "blocked_reasons": ["review_required"],
                "diff_summary": {"changed": ["member_role"]},
            },
            "authorization_decision": {"actor_role": "operations_admin"},
            "apply_transition": {"state": "preview_only"},
            "rollback_verification": {
                "target_type": "workspace",
                "target_id": "ws-001",
                "verification_status": "prepared",
                "reason_codes": ["ROLLBACK_OK"],
                "rollback_plan": {"steps": ["restore before snapshot"]},
            },
            "structured_override": {
                "override_type": "manual",
                "approved_by": "admin-1",
                "approval_role": "SUPERADMIN",
                "reason_code": "URGENT_FIX",
                "target_type": "workspace",
                "target_id": "ws-001",
                "repair_category": "workspace_upload_readiness_preview",
                "risk_level": "high",
                "reason_detail": "internal sensitive reason",
                "audit_context": {"trace": "secret"},
            },
            "structured_justification": {
                "justification_type": "case_note",
                "provided_by": "admin-2",
                "reason_code": "POLICY_CASE",
                "related_field": "entitlement",
                "target_type": "workspace",
                "target_id": "ws-001",
                "repair_category": "workspace_upload_readiness_preview",
                "reason_detail": "private detail",
                "audit_context": {"path": "private"},
            },
            "validator_result": {
                "passed": True,
                "errors": [],
                "warnings": ["MANUAL_REVIEW_REQUIRED"],
            },
        }

    def test_01_admin_preview_module_exists(self) -> None:
        self.assertTrue(self.module_exists)

    def test_02_module_imports_with_standard_library_only(self) -> None:
        self.assertIsNotNone(self.module)
        stdlib_names = set(getattr(sys, "stdlib_module_names", set()))
        approved_modules = {
            "backend.app.core.continuity_kernel_taxonomy",
            "backend.app.core.continuity_kernel_validator",
            "backend.app.core.continuity_kernel_dry_run_adapter",
            "backend.app.core.continuity_kernel_admin_preview",
        }
        tree = ast.parse(self.source_text)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
                    self.assertTrue(imported in approved_modules or imported.split(".")[0] in stdlib_names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                module_name = node.module or ""
                self.assertTrue(module_name in approved_modules or module_name.split(".")[0] in stdlib_names)

    def test_03_source_text_says_read_only_and_non_operational(self) -> None:
        self.assertIn("read-only", self.source_lower)
        self.assertIn("non-operational", self.source_lower)

    def test_04_source_text_says_it_does_not_execute_repairs(self) -> None:
        self.assertIn("does not execute repairs", self.source_lower)

    def test_05_source_text_says_it_does_not_approve_apply(self) -> None:
        self.assertIn("does not approve apply", self.source_lower)

    def test_06_source_text_says_it_does_not_schedule_apply(self) -> None:
        self.assertIn("does not schedule apply", self.source_lower)

    def test_07_source_text_says_it_does_not_write_to_the_database(self) -> None:
        self.assertIn("does not write to the database", self.source_lower)

    def test_08_source_text_says_it_does_not_queue_mint_work(self) -> None:
        self.assertIn("does not queue mint work", self.source_lower)

    def test_09_source_text_says_it_does_not_mutate_certificates(self) -> None:
        self.assertIn("does not mutate certificates", self.source_lower)

    def test_10_source_text_says_it_does_not_alter_customer_records(self) -> None:
        self.assertIn("does not alter customer records", self.source_lower)

    def test_11_build_admin_preview_returns_all_preview_output_contract_keys(self) -> None:
        preview = self.module.build_admin_preview(self._base_payload())
        self.assertEqual(
            set(preview.keys()),
            {
                "preview_id",
                "target_type",
                "target_id",
                "repair_category",
                "risk_level",
                "status",
                "blocked_reasons",
                "errors",
                "warnings",
                "diff_summary",
                "rollback_summary",
                "override_summary",
                "justification_summary",
                "validator_passed",
                "allowed_actions",
            },
        )

    def test_12_allowed_actions_never_includes_prohibited_actions(self) -> None:
        prohibited = set(self.module.PROHIBITED_ACTIONS)
        direct = set(self.module.allowed_preview_actions_for_role("SUPERADMIN", "technical_repair"))
        preview = self.module.build_admin_preview(self._base_payload())
        self.assertTrue(direct.isdisjoint(prohibited))
        self.assertTrue(set(preview["allowed_actions"]).isdisjoint(prohibited))

    def test_13_marketing_admin_gets_no_repair_execution_preview_actions(self) -> None:
        actions = self.module.allowed_preview_actions_for_role("marketing_admin", "technical_repair")
        self.assertEqual(actions, [])

    def test_14_cmo_gets_no_repair_execution_preview_actions(self) -> None:
        actions = self.module.allowed_preview_actions_for_role("CMO", "technical_repair")
        self.assertEqual(actions, [])

    def test_15_unknown_role_does_not_get_dangerous_actions(self) -> None:
        actions = self.module.allowed_preview_actions_for_role("unknown_role", "technical_repair")
        self.assertTrue(set(actions).isdisjoint(set(self.module.PROHIBITED_ACTIONS)))

    def test_16_preview_does_not_mutate_input_payload(self) -> None:
        payload = self._base_payload()
        baseline = deepcopy(payload)
        _ = self.module.build_admin_preview(payload)
        self.assertEqual(payload, baseline)

    def test_17_rollback_summary_does_not_expose_full_rollback_plan(self) -> None:
        summary = self.module.summarize_rollback(self._base_payload()["rollback_verification"])
        self.assertNotIn("rollback_plan", summary)
        self.assertIn("has_rollback_plan", summary)
        self.assertTrue(summary["has_rollback_plan"])

    def test_18_override_summary_does_not_expose_reason_detail_or_full_audit_context(self) -> None:
        summary = self.module.summarize_override(self._base_payload()["structured_override"])
        self.assertNotIn("reason_detail", summary)
        self.assertNotIn("audit_context", summary)

    def test_19_justification_summary_does_not_expose_reason_detail_or_full_audit_context(self) -> None:
        summary = self.module.summarize_justification(self._base_payload()["structured_justification"])
        self.assertNotIn("reason_detail", summary)
        self.assertNotIn("audit_context", summary)

    def test_20_missing_evidence_packet_produces_status_missing_evidence(self) -> None:
        payload = self._base_payload()
        payload.pop("evidence_packet")
        preview = self.module.build_admin_preview(payload)
        self.assertEqual(preview["status"], "missing_evidence")

    def test_21_validator_result_passed_false_produces_status_validation_failed_or_blocked(self) -> None:
        payload = self._base_payload()
        payload["validator_result"] = {"passed": False, "errors": ["E1"], "warnings": []}
        payload["evidence_packet"]["blocked_reasons"] = []
        preview = self.module.build_admin_preview(payload)
        self.assertIn(preview["status"], {"validation_failed", "blocked"})

    def test_22_preview_module_is_not_imported_in_routes_services_scripts_main(self) -> None:
        module_name = "continuity_kernel_admin_preview"
        candidates = []

        for pattern in [
            "backend/app/routes/**/*.py",
            "backend/app/services/**/*.py",
            "backend/scripts/**/*.py",
        ]:
            candidates.extend(REPO_ROOT.glob(pattern))

        for explicit in [
            REPO_ROOT / "backend" / "main.py",
            REPO_ROOT / "backend" / "app" / "main.py",
        ]:
            if explicit.exists():
                candidates.append(explicit)

        for path in candidates:
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn(module_name, text, msg=f"Unexpected preview module reference in {path}")

    def test_23_preview_module_contains_no_database_read_write_behavior(self) -> None:
        for forbidden in [
            "insert_one(",
            "update_one(",
            "delete_one(",
            "find_one(",
            "find(",
            "db[",
            "collection[",
            "session.commit(",
            "cursor.execute(",
        ]:
            self.assertNotIn(forbidden, self.source_lower)

    def test_24_preview_module_contains_no_repair_execution_behavior(self) -> None:
        for forbidden in ["execute_repair", "apply_repair", "run_repair_script", "repair_script("]:
            self.assertNotIn(forbidden, self.source_lower)

    def test_25_preview_module_contains_no_mint_queueing_behavior(self) -> None:
        for forbidden in ["queue_mint_work(", "enqueue_mint(", "mint_queue", "publish_mint"]:
            self.assertNotIn(forbidden, self.source_lower)


if __name__ == "__main__":
    unittest.main()
