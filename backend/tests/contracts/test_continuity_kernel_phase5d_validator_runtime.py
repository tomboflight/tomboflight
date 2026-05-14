from importlib import import_module
from pathlib import Path
import unittest


MODULE_PATH = "backend.app.core.continuity_kernel_validator"
REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_validator.py"


class TestContinuityKernelPhase5DValidatorRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = import_module(MODULE_PATH)
        cls.source_text = SOURCE_PATH.read_text(encoding="utf-8")

    def _valid_packet(self) -> dict:
        return {
            "dry_run_id": "dry-1",
            "evidence_packet_id": "ep-1",
            "actor_user_id": "user-1",
            "requested_by": "requester-1",
            "reviewed_by": "reviewer-1",
            "approved_by": "approver-1",
            "executed_by": "executor-1",
            "approval_role": "SUPERADMIN",
            "target_type": "workspace",
            "target_id": "target-1",
            "repair_category": "workspace_membership_repair",
            "before_snapshot": {"state": "before"},
            "proposed_after_snapshot": {"state": "after"},
            "diff_summary": "safe repair update",
            "blocked_reasons": [],
            "risk_level": "medium",
            "rollback_plan": {"steps": ["restore_before_snapshot"]},
            "idempotency_key": "idem-1",
            "created_at": "2026-05-13T00:00:00Z",
            "approved_at": "2026-05-13T00:01:00Z",
            "executed_at": "2026-05-13T00:02:00Z",
            "audit_context": "ticket=CK-1 approval trail documented",
        }

    def _valid_authorization(self) -> dict:
        return {
            "actor_user_id": "approver-1",
            "actor_role": "SUPERADMIN",
            "requested_action": "approve_apply",
            "repair_category": "workspace_membership_repair",
            "target_type": "workspace",
            "target_id": "target-1",
            "decision": "approved",
            "reason_codes": ["policy_ok"],
            "policy_source": "phase5-governance",
            "evaluated_at": "2026-05-13T00:01:00Z",
        }

    def _valid_transition(self) -> dict:
        return {
            "evidence_packet_id": "ep-1",
            "previous_state": "dry_run_created",
            "next_state": "review_requested",
            "actor_user_id": "approver-1",
            "action": "submit_for_review",
            "transition_allowed": True,
            "reason_codes": ["state_machine_ok"],
            "timestamp": "2026-05-13T00:01:30Z",
            "audit_context": "transition logged",
        }

    def _valid_rollback(self) -> dict:
        return {
            "evidence_packet_id": "ep-1",
            "rollback_plan": {"steps": ["restore_before_snapshot"]},
            "before_snapshot_ref": "snapshot-1",
            "target_type": "workspace",
            "target_id": "target-1",
            "verification_status": "verified",
            "reason_codes": ["rollback_plan_present"],
            "verified_at": "2026-05-13T00:03:00Z",
            "audit_context": "rollback verification prepared",
        }

    def test_module_imports_without_fastapi_mongo_pydantic_dependencies(self) -> None:
        self.assertIsNotNone(self.module)
        lower_source = self.source_text.lower()
        self.assertNotIn("fastapi", lower_source)
        self.assertNotIn("pymongo", lower_source)
        self.assertNotIn("motor", lower_source)
        self.assertNotIn("bson", lower_source)
        self.assertNotIn("pydantic", lower_source)

    def test_complete_valid_evidence_packet_passes_validation(self) -> None:
        result = self.module.validate_evidence_packet(self._valid_packet())
        self.assertTrue(result["passed"])

    def test_missing_required_evidence_field_fails_closed(self) -> None:
        packet = self._valid_packet()
        del packet["target_id"]
        result = self.module.validate_evidence_packet(packet)
        self.assertFalse(result["passed"])

    def test_marketing_admin_approval_fails_closed(self) -> None:
        auth = self._valid_authorization()
        auth["actor_role"] = "marketing_admin"
        result = self.module.validate_authorization_decision(auth)
        self.assertFalse(result["passed"])

    def test_invalid_state_transition_fails_closed(self) -> None:
        transition = self._valid_transition()
        transition["previous_state"] = "dry_run_created"
        transition["next_state"] = "apply_executed"
        result = self.module.validate_apply_state_transition(transition)
        self.assertFalse(result["passed"])

    def test_consumed_idempotency_key_fails_closed(self) -> None:
        result = self.module.validate_apply_request(
            self._valid_packet(),
            self._valid_authorization(),
            self._valid_transition(),
            self._valid_rollback(),
            consumed_idempotency_keys={"idem-1"},
        )
        self.assertFalse(result["passed"])

    def test_missing_rollback_plan_fails_closed(self) -> None:
        packet = self._valid_packet()
        packet["rollback_plan"] = ""
        result = self.module.validate_evidence_packet(packet)
        self.assertFalse(result["passed"])

    def test_immutable_issued_certificate_mutation_request_fails_closed(self) -> None:
        packet = self._valid_packet()
        packet["diff_summary"] = "attempt to mutate immutable issued certificate content"
        result = self.module.validate_evidence_packet(packet)
        self.assertFalse(result["passed"])

    def test_mint_queueing_directly_from_repair_fails_closed(self) -> None:
        packet = self._valid_packet()
        packet["diff_summary"] = "queue mint work directly from repair"
        result = self.module.validate_evidence_packet(packet)
        self.assertFalse(result["passed"])

    def test_customer_record_deletion_fails_closed(self) -> None:
        packet = self._valid_packet()
        packet["diff_summary"] = "delete customer record during repair"
        result = self.module.validate_evidence_packet(packet)
        self.assertFalse(result["passed"])

    def test_unknown_role_fails_closed(self) -> None:
        auth = self._valid_authorization()
        auth["actor_role"] = "unknown_role"
        result = self.module.validate_authorization_decision(auth)
        self.assertFalse(result["passed"])

    def test_unknown_repair_category_fails_closed(self) -> None:
        auth = self._valid_authorization()
        auth["repair_category"] = "unknown_category"
        result = self.module.validate_authorization_decision(auth)
        self.assertFalse(result["passed"])

    def test_high_risk_same_requester_executor_fails_without_override_and_passes_with_superadmin_override(self) -> None:
        packet = self._valid_packet()
        packet["risk_level"] = "high"
        packet["requested_by"] = "same-user"
        packet["executed_by"] = "same-user"
        packet["approval_role"] = "operations_admin"
        packet["audit_context"] = "standard flow"

        result_without_override = self.module.validate_evidence_packet(packet)
        self.assertFalse(result_without_override["passed"])

        packet["approval_role"] = "SUPERADMIN"
        packet["audit_context"] = "emergency override approved by SUPERADMIN"
        packet["override"] = {
            "override_id": "ovr-phase5d-1",
            "override_type": "SUPERADMIN_EMERGENCY_OVERRIDE",
            "requested_by": packet["requested_by"],
            "approved_by": packet["approved_by"],
            "approval_role": "SUPERADMIN",
            "reason_code": "EMERGENCY_SAFETY_EXCEPTION",
            "reason_detail": "Structured emergency override for high-risk same actor.",
            "target_type": packet["target_type"],
            "target_id": packet["target_id"],
            "repair_category": packet["repair_category"],
            "risk_level": packet["risk_level"],
            "expires_at": "2099-01-01T00:00:00Z",
            "audit_context": "phase5d structured override",
        }
        result_with_override = self.module.validate_evidence_packet(packet)
        self.assertTrue(result_with_override["passed"])

    def test_validator_result_includes_required_fields(self) -> None:
        result = self.module.validate_apply_request(
            self._valid_packet(),
            self._valid_authorization(),
            self._valid_transition(),
            self._valid_rollback(),
        )
        for field in ["validator_name", "passed", "reason_codes", "errors", "warnings", "evaluated_at"]:
            self.assertIn(field, result)

    def test_module_source_contains_non_operational_guardrail_language(self) -> None:
        lower_source = self.source_text.lower()
        self.assertIn("does not execute repairs", lower_source)
        self.assertIn("does not write to the database", lower_source)
        self.assertIn("does not queue mint work", lower_source)
        self.assertIn("does not mutate certificates", lower_source)
        self.assertIn("only validates future apply-mode evidence and governance contracts", lower_source)


if __name__ == "__main__":
    unittest.main()
