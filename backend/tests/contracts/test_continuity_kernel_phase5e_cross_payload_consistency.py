from importlib import import_module
from pathlib import Path
import unittest


MODULE_PATH = "backend.app.core.continuity_kernel_validator"
REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_validator.py"
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase5e_cross_payload_consistency.md"


class TestContinuityKernelPhase5ECrossPayloadConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = import_module(MODULE_PATH)
        cls.source_text = SOURCE_PATH.read_text(encoding="utf-8")
        cls.source_lower = cls.source_text.lower()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8")
        cls.doc_lower = cls.doc_text.lower()

    def _valid_packet(self) -> dict:
        return {
            "dry_run_id": "dry-1",
            "evidence_packet_id": "ep-1",
            "actor_user_id": "actor-1",
            "requested_by": "requester-1",
            "reviewed_by": "reviewer-1",
            "approved_by": "approver-1",
            "executed_by": "executor-1",
            "approval_role": "SUPERADMIN",
            "target_type": "workspace",
            "target_id": "workspace-1",
            "repair_category": "workspace_membership_repair",
            "before_snapshot": {"state": "before"},
            "proposed_after_snapshot": {"state": "after"},
            "diff_summary": "safe update",
            "blocked_reasons": [],
            "risk_level": "medium",
            "rollback_plan": {"steps": ["restore before_snapshot ref"]},
            "idempotency_key": "idem-1",
            "created_at": "2026-05-13T00:00:00Z",
            "approved_at": "2026-05-13T00:01:00Z",
            "executed_at": "2026-05-13T00:02:00Z",
            "audit_context": "approval trail documented",
        }

    def _valid_authorization(self) -> dict:
        return {
            "actor_user_id": "approver-1",
            "actor_role": "SUPERADMIN",
            "requested_action": "approve_apply",
            "repair_category": "workspace_membership_repair",
            "target_type": "workspace",
            "target_id": "workspace-1",
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
            "rollback_plan": {"steps": ["restore before_snapshot_ref"]},
            "before_snapshot_ref": "snapshot-1",
            "target_type": "workspace",
            "target_id": "workspace-1",
            "verification_status": "verified",
            "reason_codes": ["rollback_plan_present"],
            "verified_at": "2026-05-13T00:03:00Z",
            "audit_context": "rollback verification prepared",
        }

    def _validate(self, packet: dict | None = None, authorization: dict | None = None, transition: dict | None = None, rollback: dict | None = None, consumed_keys: set[str] | None = None) -> dict:
        return self.module.validate_apply_request(
            packet or self._valid_packet(),
            authorization or self._valid_authorization(),
            transition or self._valid_transition(),
            rollback or self._valid_rollback(),
            consumed_idempotency_keys=consumed_keys,
        )

    def test_01_fully_consistent_apply_request_passes(self) -> None:
        result = self._validate()
        self.assertTrue(result["passed"])

    def test_02_evidence_packet_id_mismatch_fails(self) -> None:
        transition = self._valid_transition()
        transition["evidence_packet_id"] = "ep-other"
        result = self._validate(transition=transition)
        self.assertFalse(result["passed"])

    def test_03_repair_category_mismatch_fails(self) -> None:
        authorization = self._valid_authorization()
        authorization["repair_category"] = "upload_readiness_repair"
        result = self._validate(authorization=authorization)
        self.assertFalse(result["passed"])

    def test_04_target_type_mismatch_fails(self) -> None:
        authorization = self._valid_authorization()
        authorization["target_type"] = "entitlement"
        result = self._validate(authorization=authorization)
        self.assertFalse(result["passed"])

    def test_05_target_id_mismatch_fails(self) -> None:
        authorization = self._valid_authorization()
        authorization["target_id"] = "workspace-2"
        result = self._validate(authorization=authorization)
        self.assertFalse(result["passed"])

    def test_06_approval_role_and_authorization_actor_role_mismatch_fails_unless_explicitly_allowed(self) -> None:
        packet = self._valid_packet()
        authorization = self._valid_authorization()
        authorization["actor_role"] = "operations_admin"
        result_without_override = self._validate(packet=packet, authorization=authorization)
        self.assertFalse(result_without_override["passed"])

        packet["audit_context"] = "approval_role_compatibility_override approved by governance"
        result_with_override = self._validate(packet=packet, authorization=authorization)
        self.assertTrue(result_with_override["passed"])

    def test_07_missing_audit_context_in_transition_fails(self) -> None:
        transition = self._valid_transition()
        transition["audit_context"] = ""
        result = self._validate(transition=transition)
        self.assertFalse(result["passed"])

    def test_08_rollback_evidence_packet_id_mismatch_fails(self) -> None:
        rollback = self._valid_rollback()
        rollback["evidence_packet_id"] = "ep-other"
        result = self._validate(rollback=rollback)
        self.assertFalse(result["passed"])

    def test_09_rollback_target_type_mismatch_fails(self) -> None:
        rollback = self._valid_rollback()
        rollback["target_type"] = "certificate"
        result = self._validate(rollback=rollback)
        self.assertFalse(result["passed"])

    def test_10_rollback_target_id_mismatch_fails(self) -> None:
        rollback = self._valid_rollback()
        rollback["target_id"] = "workspace-2"
        result = self._validate(rollback=rollback)
        self.assertFalse(result["passed"])

    def test_11_missing_rollback_plan_fails(self) -> None:
        rollback = self._valid_rollback()
        rollback["rollback_plan"] = ""
        result = self._validate(rollback=rollback)
        self.assertFalse(result["passed"])

    def test_12_blank_idempotency_key_fails_closed(self) -> None:
        packet = self._valid_packet()
        packet["idempotency_key"] = ""
        result = self._validate(packet=packet)
        self.assertFalse(result["passed"])

    def test_13_consumed_idempotency_key_fails_closed(self) -> None:
        result = self._validate(consumed_keys={"idem-1"})
        self.assertFalse(result["passed"])

    def test_14_high_risk_same_requester_executor_fails_without_override(self) -> None:
        packet = self._valid_packet()
        packet["risk_level"] = "high"
        packet["requested_by"] = "same-user"
        packet["executed_by"] = "same-user"
        packet["approval_role"] = "operations_admin"
        packet["audit_context"] = "standard flow"
        authorization = self._valid_authorization()
        authorization["actor_role"] = "operations_admin"
        result = self._validate(packet=packet, authorization=authorization)
        self.assertFalse(result["passed"])

    def test_15_high_risk_same_requester_executor_passes_only_with_superadmin_emergency_override(self) -> None:
        packet = self._valid_packet()
        packet["risk_level"] = "high"
        packet["requested_by"] = "same-user"
        packet["executed_by"] = "same-user"
        packet["approval_role"] = "SUPERADMIN"
        packet["audit_context"] = "emergency override approved by SUPERADMIN"
        result = self._validate(packet=packet)
        self.assertTrue(result["passed"])

    def test_16_cmo_marketing_admin_approval_fails(self) -> None:
        authorization = self._valid_authorization()
        authorization["actor_role"] = "CMO"
        result = self.module.validate_authorization_decision(authorization)
        self.assertFalse(result["passed"])

        authorization["actor_role"] = "marketing_admin"
        result = self.module.validate_authorization_decision(authorization)
        self.assertFalse(result["passed"])

    def test_17_prohibited_text_in_evidence_packet_fails(self) -> None:
        packet = self._valid_packet()
        packet["diff_summary"] = "attempt to bypass auth controls"
        result = self._validate(packet=packet)
        self.assertFalse(result["passed"])

    def test_18_prohibited_text_in_transition_audit_context_fails(self) -> None:
        transition = self._valid_transition()
        transition["audit_context"] = "trying to bypass audit logging for speed"
        result = self._validate(transition=transition)
        self.assertFalse(result["passed"])

    def test_19_prohibited_text_in_rollback_plan_fails(self) -> None:
        rollback = self._valid_rollback()
        rollback["rollback_plan"] = {"notes": "hard-code customer-specific production values"}
        result = self._validate(rollback=rollback)
        self.assertFalse(result["passed"])

    def test_20_validator_result_shape_remains_stable(self) -> None:
        result = self._validate()
        required_fields = ["validator_name", "passed", "reason_codes", "errors", "warnings", "evaluated_at"]
        for field in required_fields:
            self.assertIn(field, result)

    def test_21_validator_module_remains_isolated(self) -> None:
        self.assertNotIn("fastapi", self.source_lower)
        self.assertNotIn("pymongo", self.source_lower)
        self.assertNotIn("motor", self.source_lower)
        self.assertNotIn("bson", self.source_lower)
        self.assertNotIn("pydantic", self.source_lower)
        self.assertNotIn("backend.app.routes", self.source_lower)
        self.assertNotIn("backend.app.services", self.source_lower)
        self.assertNotIn("backend.scripts", self.source_lower)
        self.assertNotIn("from ..routes", self.source_lower)
        self.assertNotIn("from ..services", self.source_lower)

    def test_22_validator_source_keeps_non_operational_guardrail_language(self) -> None:
        self.assertIn("does not execute repairs", self.source_lower)
        self.assertIn("does not write to the database", self.source_lower)
        self.assertIn("does not queue mint work", self.source_lower)
        self.assertIn("does not mutate certificates", self.source_lower)


if __name__ == "__main__":
    unittest.main()
