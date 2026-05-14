from copy import deepcopy
from importlib import import_module
from pathlib import Path
import ast
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase5k_readonly_admin_preview.md"
MODULE_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_admin_preview.py"
MODULE_IMPORT = "backend.app.core.continuity_kernel_admin_preview"


class TestContinuityKernelPhase5KReadonlyAdminPreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_exists = DOC_PATH.exists()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if cls.doc_exists else ""
        cls.doc_lower = cls.doc_text.lower()

        cls.module_exists = MODULE_PATH.exists()
        cls.module_text = MODULE_PATH.read_text(encoding="utf-8") if cls.module_exists else ""
        cls.module_lower = cls.module_text.lower()
        cls.module = import_module(MODULE_IMPORT) if cls.module_exists else None

    def test_01_phase5k_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_includes_read_only_preview_purpose(self) -> None:
        self.assertIn("read-only preview purpose", self.doc_lower)
        for expected in [
            "display dry-run evidence summary",
            "display validator_result summary",
            "display blocked reasons",
            "display risk level",
            "display target selector",
            "display rollback plan summary",
            "display structured_override summary if present",
            "display structured_justification summary if present",
            "display governance state",
            "never execute repairs",
            "never approve apply",
            "never schedule apply",
            "never mutate data",
        ]:
            self.assertIn(expected, self.doc_lower)

    def test_03_doc_lists_all_preview_input_contract_keys(self) -> None:
        for value in [
            "evidence_packet",
            "authorization_decision",
            "apply_transition",
            "rollback_verification",
            "structured_override",
            "structured_justification",
            "validator_result",
        ]:
            self.assertIn(value, self.doc_text)

    def test_04_doc_lists_all_preview_output_contract_keys(self) -> None:
        for value in [
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
        ]:
            self.assertIn(value, self.doc_text)

    def test_05_doc_lists_allowed_read_only_actions(self) -> None:
        for value in [
            "view_preview",
            "copy_case_summary",
            "export_dry_run_summary",
            "request_review",
        ]:
            self.assertIn(value, self.doc_text)

    def test_06_doc_lists_prohibited_actions(self) -> None:
        for value in [
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
        ]:
            self.assertIn(value, self.doc_text)

    def test_07_doc_lists_all_admin_preview_status_values(self) -> None:
        for value in [
            "preview_ready",
            "blocked",
            "invalid_payload",
            "missing_evidence",
            "validation_failed",
            "review_required",
        ]:
            self.assertIn(value, self.doc_text)

    def test_08_doc_includes_officer_visibility_rules(self) -> None:
        for value in [
            "SUPERADMIN may view all preview categories",
            "EXECUTIVE_TECH_ADMIN may view technical repair previews",
            "operations_admin may view workspace/upload/viewer/readiness previews",
            "finance_admin may view billing/order/payment previews",
            "marketing_admin may not view repair execution preview actions",
            "CMO/marketing_admin cannot approve or execute anything from preview",
        ]:
            self.assertIn(value, self.doc_text)

    def test_09_doc_states_marketing_admin_cannot_approve_or_execute(self) -> None:
        self.assertIn("cmo/marketing_admin cannot approve or execute anything from preview", self.doc_lower)

    def test_10_doc_includes_non_operational_guardrails(self) -> None:
        for value in [
            "phase 5k does not wire preview into admin ui",
            "phase 5k does not create backend routes",
            "phase 5k does not create apply mode",
            "phase 5k does not create repair scripts",
            "phase 5k does not touch live data",
            "phase 5k only defines read-only preview contracts and tests",
        ]:
            self.assertIn(value, self.doc_lower)

    def test_11_optional_module_imports_allow_stdlib_and_approved_isolated_core_modules_only(self) -> None:
        if not self.module_exists:
            self.skipTest("Optional Phase 5K admin preview module was not added")

        stdlib_names = set(getattr(sys, "stdlib_module_names", set()))
        approved_modules = {
            "backend.app.core.continuity_kernel_taxonomy",
            "backend.app.core.continuity_kernel_validator",
            "backend.app.core.continuity_kernel_dry_run_adapter",
            "backend.app.core.continuity_kernel_admin_preview",
        }
        tree = ast.parse(self.module_text)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
                    root = imported.split(".")[0]
                    self.assertTrue(
                        imported in approved_modules or root in stdlib_names,
                        msg=f"Non-approved import found: {imported}",
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    self.fail("Relative imports are not allowed in optional preview module")
                module_name = node.module or ""
                root = module_name.split(".")[0]
                self.assertTrue(
                    module_name in approved_modules or root in stdlib_names,
                    msg=f"Non-approved import found: {module_name}",
                )

    def test_12_optional_module_has_no_fastapi_mongo_pydantic_routes_services_scripts_imports(self) -> None:
        if not self.module_exists:
            self.skipTest("Optional Phase 5K admin preview module was not added")

        for forbidden in [
            "fastapi",
            "pydantic",
            "pymongo",
            "motor",
            "mongo",
            "stripe",
            "web3",
            "backend.app.routes",
            "backend.app.services",
            "backend.scripts",
            "from ..routes",
            "from ..services",
            "from ..scripts",
            "from backend.app.routes",
            "from backend.app.services",
            "from backend.scripts",
        ]:
            self.assertNotIn(forbidden, self.module_lower)

    def test_13_optional_module_source_says_read_only_and_non_operational(self) -> None:
        if not self.module_exists:
            self.skipTest("Optional Phase 5K admin preview module was not added")

        self.assertIn("read-only", self.module_lower)
        self.assertIn("non-operational", self.module_lower)

    def test_14_optional_module_build_admin_preview_returns_output_contract_keys(self) -> None:
        if not self.module_exists:
            self.skipTest("Optional Phase 5K admin preview module was not added")

        payload = {
            "evidence_packet": {
                "target_type": "workspace",
                "target_id": "ws-001",
                "repair_category": "workspace_membership_repair",
                "risk_level": "high",
                "blocked_reasons": ["review_required"],
                "diff_summary": {"changed": ["entitlement"]},
            },
            "authorization_decision": {"decision": "not_approved"},
            "apply_transition": {"state": "preview_only"},
            "rollback_verification": {"steps": ["restore snapshot"]},
            "structured_override": {"override_id": "ovr-001", "reason": "breakglass"},
            "structured_justification": {"justification_id": "jus-001", "rationale": "operator note"},
            "validator_result": {
                "passed": False,
                "errors": ["AUTHORIZATION_NOT_APPROVED"],
                "warnings": ["MANUAL_REVIEW_REQUIRED"],
            },
        }

        preview = self.module.build_admin_preview(payload)
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

    def test_15_optional_module_allowed_actions_never_include_apply_or_mutation_actions(self) -> None:
        if not self.module_exists:
            self.skipTest("Optional Phase 5K admin preview module was not added")

        prohibited = {
            "approve_apply",
            "schedule_apply",
            "execute_apply",
            "rollback_apply",
            "queue_mint",
            "mutate_entitlement",
            "mutate_workspace_member",
            "mutate_certificate",
            "delete_customer_record",
        }

        actions = self.module.allowed_preview_actions_for_role("SUPERADMIN", "technical_repair")
        self.assertTrue(set(actions).isdisjoint(prohibited))

        payload = {
            "evidence_packet": {"repair_category": "technical_repair"},
            "authorization_decision": {},
            "apply_transition": {},
            "rollback_verification": {},
            "structured_override": None,
            "structured_justification": None,
            "validator_result": {},
        }
        preview = self.module.build_admin_preview(payload)
        self.assertTrue(set(preview.get("allowed_actions", [])).isdisjoint(prohibited))

    def test_16_optional_module_marketing_admin_gets_no_repair_execution_preview_actions(self) -> None:
        if not self.module_exists:
            self.skipTest("Optional Phase 5K admin preview module was not added")

        actions = self.module.allowed_preview_actions_for_role("marketing_admin", "technical_repair")
        forbidden = {"approve_apply", "schedule_apply", "execute_apply", "rollback_apply", "queue_mint"}
        self.assertTrue(set(actions).isdisjoint(forbidden))

    def test_17_optional_module_preview_does_not_mutate_input_payload(self) -> None:
        if not self.module_exists:
            self.skipTest("Optional Phase 5K admin preview module was not added")

        payload = {
            "evidence_packet": {
                "target_type": "workspace",
                "target_id": "ws-001",
                "repair_category": "workspace_membership_repair",
                "risk_level": "medium",
                "blocked_reasons": ["policy_hold"],
                "diff_summary": {"changed": ["member_role"]},
            },
            "authorization_decision": {"decision": "not_approved"},
            "apply_transition": {"state": "preview_only"},
            "rollback_verification": {"steps": ["step-1"]},
            "structured_override": {"override_id": "ovr-001", "internal": {"secret": "value"}},
            "structured_justification": {
                "justification_id": "jus-001",
                "internal": {"private": "details"},
            },
            "validator_result": {"passed": False, "errors": ["x"], "warnings": ["y"]},
        }
        baseline = deepcopy(payload)

        _ = self.module.build_admin_preview(payload)
        self.assertEqual(payload, baseline)

    def test_18_optional_module_summaries_do_not_expose_full_sensitive_payloads(self) -> None:
        if not self.module_exists:
            self.skipTest("Optional Phase 5K admin preview module was not added")

        rollback_input = {
            "plan": ["restore"],
            "sensitive_token": "do-not-expose",
            "credentials": {"api_key": "do-not-expose"},
        }
        override_input = {
            "override_id": "ovr-001",
            "approved_by": "officer",
            "secret_material": "do-not-expose",
        }
        justification_input = {
            "justification_id": "jus-001",
            "summary": "needed for dry-run",
            "internal_notes": "do-not-expose",
        }

        rollback_summary = self.module.summarize_rollback(rollback_input)
        override_summary = self.module.summarize_override(override_input)
        justification_summary = self.module.summarize_justification(justification_input)

        self.assertNotEqual(rollback_summary, rollback_input)
        self.assertNotEqual(override_summary, override_input)
        self.assertNotEqual(justification_summary, justification_input)

        serialized = (str(rollback_summary) + str(override_summary) + str(justification_summary)).lower()
        self.assertNotIn("do-not-expose", serialized)
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("secret_material", serialized)
        self.assertNotIn("internal_notes", serialized)


if __name__ == "__main__":
    unittest.main()
