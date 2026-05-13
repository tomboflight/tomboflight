from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend/docs/governance/continuity_kernel_phase5c_validator_schema.md"


class TestContinuityKernelPhase5CValidatorSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8")
        cls.doc_lower = cls.doc_text.lower()

    def test_phase5c_validator_schema_doc_exists(self) -> None:
        self.assertTrue(DOC_PATH.is_file(), "Phase 5C validator/schema doc must exist.")

    def test_doc_includes_all_five_schema_names(self) -> None:
        required_schema_names = [
            "EvidencePacketSchema",
            "AuthorizationDecisionSchema",
            "ApplyStateTransitionSchema",
            "RollbackVerificationSchema",
            "ValidatorResultSchema",
        ]
        missing = [name for name in required_schema_names if name not in self.doc_text]
        self.assertFalse(missing, f"Missing schema names: {missing}")

    def test_doc_includes_required_evidence_packet_schema_fields(self) -> None:
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
        self.assertFalse(missing, f"Missing EvidencePacketSchema fields: {missing}")

    def test_doc_includes_required_authorization_decision_schema_fields(self) -> None:
        required_fields = [
            "actor_user_id",
            "actor_role",
            "requested_action",
            "repair_category",
            "target_type",
            "target_id",
            "decision",
            "reason_codes",
            "policy_source",
            "evaluated_at",
        ]
        missing = [field for field in required_fields if field not in self.doc_text]
        self.assertFalse(missing, f"Missing AuthorizationDecisionSchema fields: {missing}")

    def test_doc_includes_required_apply_state_transition_schema_fields(self) -> None:
        required_fields = [
            "evidence_packet_id",
            "previous_state",
            "next_state",
            "actor_user_id",
            "action",
            "transition_allowed",
            "reason_codes",
            "timestamp",
            "audit_context",
        ]
        missing = [field for field in required_fields if field not in self.doc_text]
        self.assertFalse(missing, f"Missing ApplyStateTransitionSchema fields: {missing}")

    def test_doc_includes_required_rollback_verification_schema_fields(self) -> None:
        required_fields = [
            "evidence_packet_id",
            "rollback_plan",
            "before_snapshot_ref",
            "target_type",
            "target_id",
            "verification_status",
            "reason_codes",
            "verified_at",
            "audit_context",
        ]
        missing = [field for field in required_fields if field not in self.doc_text]
        self.assertFalse(missing, f"Missing RollbackVerificationSchema fields: {missing}")

    def test_doc_includes_required_validator_result_schema_fields(self) -> None:
        required_fields = [
            "validator_name",
            "passed",
            "reason_codes",
            "errors",
            "warnings",
            "evaluated_at",
        ]
        missing = [field for field in required_fields if field not in self.doc_text]
        self.assertFalse(missing, f"Missing ValidatorResultSchema fields: {missing}")

    def test_doc_includes_fail_closed_validation_rules(self) -> None:
        self.assertRegex(self.doc_lower, r"fail-closed\s+validation\s+rules")
        self.assertIn("fail closed if required fields are missing", self.doc_lower)
        self.assertIn("fail closed if apply state transition is not allowed", self.doc_lower)
        self.assertIn("fail closed if idempotency_key is already consumed", self.doc_lower)
        self.assertIn("fail closed if rollback_plan is missing", self.doc_lower)
        self.assertIn("fail closed if audit_context is missing", self.doc_lower)
        self.assertIn("fail closed if actor role does not match repair category", self.doc_lower)

    def test_doc_prohibits_cmo_marketing_admin_approval(self) -> None:
        self.assertIn("fail closed if cmo/marketing_admin attempts approval", self.doc_lower)

    def test_doc_prohibits_immutable_issued_certificate_mutation(self) -> None:
        self.assertIn(
            "fail closed if immutable issued certificate mutation is requested",
            self.doc_lower,
        )

    def test_doc_prohibits_mint_queueing_directly_from_repair(self) -> None:
        self.assertIn(
            "fail closed if mint queueing is requested directly from repair",
            self.doc_lower,
        )

    def test_doc_prohibits_customer_record_deletion(self) -> None:
        self.assertIn("fail closed if customer record deletion is requested", self.doc_lower)

    def test_doc_states_phase5c_non_implementation_guardrail(self) -> None:
        self.assertIn("phase 5c does not implement validators in runtime code", self.doc_lower)
        self.assertIn("phase 5c does not create repair scripts", self.doc_lower)
        self.assertIn("phase 5c does not modify backend/app schemas", self.doc_lower)


if __name__ == "__main__":
    unittest.main()
