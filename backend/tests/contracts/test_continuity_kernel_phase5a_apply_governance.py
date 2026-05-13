from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend/docs/governance/continuity_kernel_phase5a_apply_governance.md"


class TestContinuityKernelPhase5AApplyGovernance(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8")
        cls.doc_lower = cls.doc_text.lower()

    def test_phase5a_governance_doc_exists(self) -> None:
        self.assertTrue(DOC_PATH.is_file(), "Phase 5A governance doc must exist.")

    def test_doc_states_dry_run_remains_default(self) -> None:
        self.assertRegex(self.doc_lower, r"dry-run\s+remains\s+the\s+default")

    def test_doc_states_apply_mode_is_never_automatic(self) -> None:
        self.assertRegex(self.doc_lower, r"apply\s+mode\s+is\s+never\s+automatic")

    def test_doc_requires_officer_authorization(self) -> None:
        self.assertRegex(self.doc_lower, r"apply\s+mode\s+must\s+require\s+explicit\s+officer\s+authorization")

    def test_doc_requires_prior_dry_run_evidence(self) -> None:
        self.assertRegex(self.doc_lower, r"apply\s+mode\s+must\s+require\s+prior\s+dry-run\s+evidence")

    def test_doc_includes_officer_approval_matrix_roles(self) -> None:
        required_roles = [
            "SUPERADMIN",
            "EXECUTIVE_TECH_ADMIN",
            "operations_admin",
            "finance_admin",
            "marketing_admin",
        ]
        missing = [role for role in required_roles if role not in self.doc_text]
        self.assertFalse(missing, f"Missing approval-matrix roles: {missing}")

    def test_doc_states_cmo_marketing_admin_cannot_approve_execution(self) -> None:
        self.assertIn("cmo / marketing_admin cannot approve repair execution", self.doc_lower)

    def test_doc_includes_required_evidence_packet_fields(self) -> None:
        required_fields = [
            "dry_run_id",
            "actor_user_id",
            "requested_by",
            "approved_by",
            "approval_role",
            "target_type",
            "target_id",
            "repair_category",
            "before_snapshot",
            "proposed_after_snapshot",
            "diff_summary",
            "blocked_reasons",
            "risk_level",
            "rollback_plan",
            "idempotency_key",
            "timestamp",
            "audit_context",
        ]
        missing = [field for field in required_fields if field not in self.doc_text]
        self.assertFalse(missing, f"Missing required evidence packet fields: {missing}")

    def test_doc_includes_prohibited_apply_actions(self) -> None:
        required_phrases = [
            "automatic apply after dry-run",
            "apply without officer approval",
            "apply without audit logging",
            "mutating immutable issued certificates",
            "queueing mint work directly from a repair action",
            "deleting customer records as part of repair",
        ]
        missing = [phrase for phrase in required_phrases if phrase not in self.doc_lower]
        self.assertFalse(missing, f"Missing prohibited action language: {missing}")

    def test_doc_includes_apply_mode_state_machine_states(self) -> None:
        required_states = [
            "dry_run_created",
            "review_requested",
            "officer_reviewing",
            "approved_for_apply",
            "rejected",
            "apply_scheduled",
            "apply_executed",
            "apply_failed",
            "rollback_required",
            "rollback_completed",
            "audit_closed",
        ]
        missing = [state for state in required_states if re.search(rf"\b{re.escape(state)}\b", self.doc_text) is None]
        self.assertFalse(missing, f"Missing apply-mode states: {missing}")

    def test_doc_states_phase5a_non_implementation_guardrail(self) -> None:
        self.assertIn("this phase does not implement apply mode", self.doc_lower)
        self.assertIn("this phase does not create repair scripts", self.doc_lower)


if __name__ == "__main__":
    unittest.main()
