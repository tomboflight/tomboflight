from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend/docs/governance/continuity_kernel_phase5b_apply_contracts.md"


class TestContinuityKernelPhase5BApplyContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8")
        cls.doc_lower = cls.doc_text.lower()

    def test_phase5b_contract_doc_exists(self) -> None:
        self.assertTrue(DOC_PATH.is_file(), "Phase 5B contract doc must exist.")

    def test_doc_includes_authorization_contract(self) -> None:
        self.assertIn("Authorization Contract", self.doc_text)

    def test_doc_includes_evidence_packet_contract(self) -> None:
        self.assertIn("Evidence Packet Contract", self.doc_text)

    def test_doc_includes_approval_workflow_contract(self) -> None:
        self.assertIn("Approval Workflow Contract", self.doc_text)

    def test_doc_includes_apply_executor_contract(self) -> None:
        self.assertIn("Apply Executor Contract", self.doc_text)

    def test_doc_includes_rollback_verification_contract(self) -> None:
        self.assertIn("Rollback Verification Contract", self.doc_text)

    def test_doc_includes_audit_transition_contract(self) -> None:
        self.assertIn("Audit Transition Contract", self.doc_text)

    def test_doc_states_cmo_marketing_admin_cannot_approve_execution(self) -> None:
        self.assertIn("cmo/marketing_admin cannot approve repair execution", self.doc_lower)

    def test_doc_includes_all_evidence_packet_fields(self) -> None:
        required_fields = [
            "dry_run_id",
            "evidence_packet_id",
            "actor_user_id",
            "requested_by",
            "reviewed_by",
            "approved_by",
            "executed_by",
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
            "created_at",
            "approved_at",
            "executed_at",
            "audit_context",
        ]
        missing = [field for field in required_fields if field not in self.doc_text]
        self.assertFalse(missing, f"Missing required evidence packet fields: {missing}")

    def test_doc_includes_all_allowed_workflow_transitions(self) -> None:
        required_transitions = [
            "dry_run_created -> review_requested",
            "review_requested -> officer_reviewing",
            "officer_reviewing -> approved_for_apply",
            "officer_reviewing -> rejected",
            "approved_for_apply -> apply_scheduled",
            "apply_scheduled -> apply_executed",
            "apply_scheduled -> apply_failed",
            "apply_failed -> rollback_required",
            "rollback_required -> rollback_completed",
            "apply_executed -> audit_closed",
            "rollback_completed -> audit_closed",
        ]
        missing = [
            transition
            for transition in required_transitions
            if re.search(rf"\b{re.escape(transition)}\b", self.doc_text) is None
        ]
        self.assertFalse(missing, f"Missing workflow transitions: {missing}")

    def test_doc_prohibits_guardrail_violations(self) -> None:
        required_phrases = [
            "must never queue mint work directly",
            "must never mutate immutable issued certificates",
            "must never delete customer records",
            "must never bypass auth, entitlement, verification, mint readiness, audit logging, or officer permissions",
        ]
        missing = [phrase for phrase in required_phrases if phrase not in self.doc_lower]
        self.assertFalse(missing, f"Missing prohibited behavior language: {missing}")

    def test_doc_states_non_implementation_guardrail(self) -> None:
        self.assertIn("phase 5b does not implement apply mode", self.doc_lower)
        self.assertIn("phase 5b does not create repair scripts", self.doc_lower)


if __name__ == "__main__":
    unittest.main()
