from importlib import import_module
from pathlib import Path
import unittest


MODULE_PATH = "backend.app.core.continuity_kernel_validator"
REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_validator.py"
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase5f_structured_overrides.md"


class TestContinuityKernelPhase5FStructuredOverrides(unittest.TestCase):
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
            "rollback_plan": {"steps": ["restore before_snapshot_ref"]},
            "idempotency_key": "idem-1",
            "created_at": "2026-05-14T00:00:00Z",
            "approved_at": "2026-05-14T00:01:00Z",
            "executed_at": "2026-05-14T00:02:00Z",
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
            "policy_source": "phase5f-governance",
            "evaluated_at": "2026-05-14T00:01:00Z",
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
            "timestamp": "2026-05-14T00:01:30Z",
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
            "verified_at": "2026-05-14T00:03:00Z",
            "audit_context": "rollback verification prepared",
        }

    def _valid_structured_override(self, packet: dict | None = None) -> dict:
        scoped_packet = packet or self._valid_packet()
        return {
            "override_id": "ovr-1",
            "override_type": "SUPERADMIN_EMERGENCY_OVERRIDE",
            "requested_by": scoped_packet["requested_by"],
            "approved_by": scoped_packet["approved_by"],
            "approval_role": "SUPERADMIN",
            "reason_code": "EMERGENCY_SAFETY_EXCEPTION",
            "reason_detail": "Emergency governance-approved override for isolated validation.",
            "target_type": scoped_packet["target_type"],
            "target_id": scoped_packet["target_id"],
            "repair_category": scoped_packet["repair_category"],
            "risk_level": scoped_packet["risk_level"],
            "expires_at": "2099-01-01T00:00:00Z",
            "audit_context": "formal override trail",
        }

    def _valid_structured_justification(self, packet: dict | None = None) -> dict:
        scoped_packet = packet or self._valid_packet()
        return {
            "justification_id": "just-1",
            "justification_type": "APPROVED_BY_ACTOR_MISMATCH",
            "provided_by": "compliance-officer-1",
            "reason_code": "DELEGATED_APPROVAL_PATH",
            "reason_detail": "Delegated approver is formally recorded and traceable.",
            "related_field": "approved_by",
            "target_type": scoped_packet["target_type"],
            "target_id": scoped_packet["target_id"],
            "repair_category": scoped_packet["repair_category"],
            "audit_context": "formal mismatch justification",
        }

    def _validate(self, packet: dict, authorization: dict, transition: dict, rollback: dict | None = None) -> dict:
        return self.module.validate_apply_request(
            packet,
            authorization,
            transition,
            rollback or self._valid_rollback(),
        )

    def test_01_structured_override_doc_exists(self) -> None:
        self.assertTrue(DOC_PATH.exists())

    def test_02_structured_override_schema_fields_are_documented(self) -> None:
        for field in [
            "override_id",
            "override_type",
            "requested_by",
            "approved_by",
            "approval_role",
            "reason_code",
            "reason_detail",
            "target_type",
            "target_id",
            "repair_category",
            "risk_level",
            "expires_at",
            "audit_context",
        ]:
            self.assertIn(field, self.doc_text)

    def test_03_structured_justification_schema_fields_are_documented(self) -> None:
        for field in [
            "justification_id",
            "justification_type",
            "provided_by",
            "reason_code",
            "reason_detail",
            "related_field",
            "target_type",
            "target_id",
            "repair_category",
            "audit_context",
        ]:
            self.assertIn(field, self.doc_text)

    def test_04_validate_structured_override_passes_with_complete_superadmin_emergency_override(self) -> None:
        packet = self._valid_packet()
        packet["risk_level"] = "high"
        override = self._valid_structured_override(packet)
        result = self.module.validate_structured_override(override, packet=packet)
        self.assertTrue(result["passed"])

    def test_05_validate_structured_override_fails_when_override_is_free_text(self) -> None:
        result = self.module.validate_structured_override("emergency override approved by superadmin")
        self.assertFalse(result["passed"])

    def test_06_validate_structured_override_fails_when_required_fields_missing(self) -> None:
        result = self.module.validate_structured_override({"override_type": "SUPERADMIN_EMERGENCY_OVERRIDE"})
        self.assertFalse(result["passed"])

    def test_07_validate_structured_override_fails_for_unknown_override_type(self) -> None:
        packet = self._valid_packet()
        override = self._valid_structured_override(packet)
        override["override_type"] = "UNKNOWN_OVERRIDE_TYPE"
        result = self.module.validate_structured_override(override, packet=packet)
        self.assertFalse(result["passed"])

    def test_08_validate_structured_override_fails_for_marketing_admin_or_cmo(self) -> None:
        packet = self._valid_packet()
        override = self._valid_structured_override(packet)
        override["approval_role"] = "CMO"
        result = self.module.validate_structured_override(override, packet=packet)
        self.assertFalse(result["passed"])

    def test_09_validate_structured_override_fails_on_packet_scope_mismatch(self) -> None:
        packet = self._valid_packet()
        override = self._valid_structured_override(packet)
        override["target_id"] = "workspace-2"
        result = self.module.validate_structured_override(override, packet=packet)
        self.assertFalse(result["passed"])

    def test_10_validate_structured_override_fails_on_prohibited_action_signal(self) -> None:
        packet = self._valid_packet()
        override = self._valid_structured_override(packet)
        override["reason_detail"] = "queue mint work directly from repair"
        result = self.module.validate_structured_override(override, packet=packet)
        self.assertFalse(result["passed"])

    def test_11_validate_structured_justification_passes_with_complete_approved_by_mismatch_justification(self) -> None:
        packet = self._valid_packet()
        justification = self._valid_structured_justification(packet)
        result = self.module.validate_structured_justification(justification, packet=packet)
        self.assertTrue(result["passed"])

    def test_12_validate_structured_justification_fails_when_justification_is_free_text(self) -> None:
        result = self.module.validate_structured_justification("approved_by mismatch justified")
        self.assertFalse(result["passed"])

    def test_13_validate_structured_justification_fails_when_required_fields_missing(self) -> None:
        result = self.module.validate_structured_justification({"justification_type": "APPROVED_BY_ACTOR_MISMATCH"})
        self.assertFalse(result["passed"])

    def test_14_validate_structured_justification_fails_for_unknown_justification_type(self) -> None:
        packet = self._valid_packet()
        justification = self._valid_structured_justification(packet)
        justification["justification_type"] = "UNKNOWN_JUSTIFICATION_TYPE"
        result = self.module.validate_structured_justification(justification, packet=packet)
        self.assertFalse(result["passed"])

    def test_15_validate_structured_justification_fails_for_marketing_admin_or_cmo_attempting_repair_approval(self) -> None:
        packet = self._valid_packet()
        justification = self._valid_structured_justification(packet)
        justification["provided_by"] = "marketing_admin"
        justification["reason_detail"] = "approve repair execution for speed"
        result = self.module.validate_structured_justification(justification, packet=packet)
        self.assertFalse(result["passed"])

    def test_16_validate_structured_justification_fails_on_packet_scope_mismatch(self) -> None:
        packet = self._valid_packet()
        justification = self._valid_structured_justification(packet)
        justification["repair_category"] = "upload_readiness_repair"
        result = self.module.validate_structured_justification(justification, packet=packet)
        self.assertFalse(result["passed"])

    def test_17_high_risk_same_requester_executor_fails_with_old_free_text_override_only(self) -> None:
        packet = self._valid_packet()
        packet["risk_level"] = "high"
        packet["requested_by"] = "same-user"
        packet["executed_by"] = "same-user"
        packet["approval_role"] = "SUPERADMIN"
        packet["audit_context"] = "emergency override approved by SUPERADMIN"

        result = self._validate(packet, self._valid_authorization(), self._valid_transition())
        self.assertFalse(result["passed"])
        self.assertIn("STRUCTURED_OVERRIDE_REQUIRED", result["reason_codes"])

    def test_18_high_risk_same_requester_executor_passes_with_valid_structured_superadmin_emergency_override(self) -> None:
        packet = self._valid_packet()
        packet["risk_level"] = "high"
        packet["requested_by"] = "same-user"
        packet["executed_by"] = "same-user"
        packet["approval_role"] = "SUPERADMIN"
        packet["override"] = self._valid_structured_override(packet)

        result = self._validate(packet, self._valid_authorization(), self._valid_transition())
        self.assertTrue(result["passed"])

    def test_19_executive_tech_admin_finance_only_repair_fails_without_structured_ceo_superadmin_override(self) -> None:
        packet = self._valid_packet()
        packet["approval_role"] = "EXECUTIVE_TECH_ADMIN"
        packet["repair_category"] = "billing_order_payment_repair"

        authorization = self._valid_authorization()
        authorization["actor_role"] = "EXECUTIVE_TECH_ADMIN"
        authorization["repair_category"] = "billing_order_payment_repair"

        result = self._validate(packet, authorization, self._valid_transition())
        self.assertFalse(result["passed"])
        self.assertIn("STRUCTURED_OVERRIDE_REQUIRED", result["reason_codes"])

    def test_20_executive_tech_admin_finance_only_repair_passes_only_with_valid_structured_ceo_superadmin_override(self) -> None:
        packet = self._valid_packet()
        packet["approval_role"] = "EXECUTIVE_TECH_ADMIN"
        packet["repair_category"] = "billing_order_payment_repair"

        finance_override = {
            "override_id": "ovr-finance-1",
            "override_type": "CEO_APPROVED_FINANCE_OVERRIDE",
            "requested_by": packet["requested_by"],
            "approved_by": "ceo-1",
            "approval_role": "CEO",
            "reason_code": "FINANCE_TECH_SCOPE_EXCEPTION",
            "reason_detail": "CEO approved isolated finance scope exception.",
            "target_type": packet["target_type"],
            "target_id": packet["target_id"],
            "repair_category": packet["repair_category"],
            "risk_level": packet["risk_level"],
            "expires_at": "2099-01-01T00:00:00Z",
            "audit_context": "finance override trail",
        }
        packet["override"] = finance_override

        authorization = self._valid_authorization()
        authorization["actor_role"] = "EXECUTIVE_TECH_ADMIN"
        authorization["repair_category"] = "billing_order_payment_repair"
        authorization["override"] = finance_override

        result = self._validate(packet, authorization, self._valid_transition())
        self.assertTrue(result["passed"])

    def test_21_approved_by_mismatch_fails_without_structured_justification(self) -> None:
        packet = self._valid_packet()
        packet["approved_by"] = "different-approver"
        result = self._validate(packet, self._valid_authorization(), self._valid_transition())
        self.assertFalse(result["passed"])
        self.assertIn("STRUCTURED_JUSTIFICATION_REQUIRED", result["reason_codes"])

    def test_22_approved_by_mismatch_passes_with_valid_structured_justification(self) -> None:
        packet = self._valid_packet()
        packet["approved_by"] = "different-approver"
        packet["justification"] = self._valid_structured_justification(packet)

        result = self._validate(packet, self._valid_authorization(), self._valid_transition())
        self.assertTrue(result["passed"])

    def test_23_transition_actor_traceability_mismatch_fails_without_structured_justification(self) -> None:
        transition = self._valid_transition()
        transition["actor_user_id"] = "untraceable-actor"

        result = self._validate(self._valid_packet(), self._valid_authorization(), transition)
        self.assertFalse(result["passed"])
        self.assertIn("STRUCTURED_JUSTIFICATION_REQUIRED", result["reason_codes"])

    def test_24_transition_actor_traceability_mismatch_passes_with_valid_structured_justification(self) -> None:
        packet = self._valid_packet()
        transition = self._valid_transition()
        transition["actor_user_id"] = "untraceable-actor"
        transition["justification"] = {
            "justification_id": "just-trace-1",
            "justification_type": "TRANSITION_ACTOR_TRACEABILITY",
            "provided_by": "compliance-officer-1",
            "reason_code": "TRACE_LINKED_VIA_GOVERNANCE_RECORD",
            "reason_detail": "Transition actor is traceable through governance actor trail.",
            "related_field": "transition.actor_user_id",
            "target_type": packet["target_type"],
            "target_id": packet["target_id"],
            "repair_category": packet["repair_category"],
            "audit_context": "traceability justification",
        }

        result = self._validate(packet, self._valid_authorization(), transition)
        self.assertTrue(result["passed"])

    def test_25_validator_module_remains_isolated(self) -> None:
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

    def test_26_validator_source_keeps_non_operational_guardrail_language(self) -> None:
        self.assertIn("does not execute repairs", self.source_lower)
        self.assertIn("does not write to the database", self.source_lower)
        self.assertIn("does not queue mint work", self.source_lower)
        self.assertIn("does not mutate certificates", self.source_lower)


if __name__ == "__main__":
    unittest.main()
