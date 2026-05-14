from importlib import import_module
from pathlib import Path
import unittest


MODULE_PATH = "backend.app.core.continuity_kernel_validator"
REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_validator.py"
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase5g_payload_placement.md"


class TestContinuityKernelPhase5GPayloadPlacement(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = import_module(MODULE_PATH)
        cls.source_text = SOURCE_PATH.read_text(encoding="utf-8")
        cls.source_lower = cls.source_text.lower()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if DOC_PATH.exists() else ""
        cls.doc_lower = cls.doc_text.lower()

    def test_01_phase5g_payload_placement_doc_exists(self) -> None:
        self.assertTrue(DOC_PATH.exists())

    def test_02_doc_includes_all_canonical_top_level_payload_keys(self) -> None:
        for key in [
            "evidence_packet",
            "authorization_decision",
            "apply_transition",
            "rollback_verification",
            "structured_override",
            "structured_justification",
            "validator_result",
        ]:
            self.assertIn(key, self.doc_text)

    def test_03_doc_says_evidence_packet_is_required(self) -> None:
        self.assertIn("evidence_packet is required", self.doc_lower)

    def test_04_doc_says_authorization_decision_is_required(self) -> None:
        self.assertIn("authorization_decision is required", self.doc_lower)

    def test_05_doc_says_apply_transition_is_required(self) -> None:
        self.assertIn("apply_transition is required", self.doc_lower)

    def test_06_doc_says_rollback_verification_is_required_for_stored_state_apply_requests(self) -> None:
        self.assertIn(
            "rollback_verification is required for any apply request that can affect stored state",
            self.doc_lower,
        )

    def test_07_doc_says_structured_override_must_be_top_level_when_used(self) -> None:
        self.assertIn("structured_override must live at top-level key structured_override when used", self.doc_lower)

    def test_08_doc_says_structured_justification_must_be_top_level_when_used(self) -> None:
        self.assertIn(
            "structured_justification must live at top-level key structured_justification when used",
            self.doc_lower,
        )

    def test_09_doc_says_validator_result_is_output_only_not_user_input_for_approval(self) -> None:
        self.assertIn("validator_result must never be accepted as user input for approval", self.doc_lower)
        self.assertIn("it is output only", self.doc_lower)

    def test_10_doc_lists_all_producer_responsibilities(self) -> None:
        for producer in [
            "dry_run_engine",
            "authorization_policy",
            "state_machine",
            "rollback_planner",
            "officer_review",
            "reviewer_notes",
            "continuity_kernel_validator",
        ]:
            self.assertIn(producer, self.doc_text)

    def test_11_doc_forbids_frontend_creating_approved_authorization_decision(self) -> None:
        self.assertIn("frontend must not create approved authorization_decision", self.doc_lower)

    def test_12_doc_forbids_frontend_creating_validator_result(self) -> None:
        self.assertIn("frontend must not create validator_result", self.doc_lower)

    def test_13_doc_forbids_admin_ui_bypassing_validator(self) -> None:
        self.assertIn("admin ui must not bypass validator", self.doc_lower)

    def test_14_doc_forbids_structured_override_in_free_text_audit_context(self) -> None:
        self.assertIn("no producer may place structured_override inside free-text audit_context", self.doc_lower)

    def test_15_doc_forbids_structured_justification_in_free_text_audit_context(self) -> None:
        self.assertIn("no producer may place structured_justification inside free-text audit_context", self.doc_lower)

    def test_16_doc_forbids_legacy_free_text_override_phrases_as_approval(self) -> None:
        self.assertIn("no producer may use legacy free-text override phrases as approval", self.doc_lower)

    def test_17_doc_includes_migration_phases_a_through_g(self) -> None:
        for phase in [
            "phase a:",
            "phase b:",
            "phase c:",
            "phase d:",
            "phase e:",
            "phase f:",
            "phase g:",
        ]:
            self.assertIn(phase, self.doc_lower)

    def test_18_doc_states_no_existing_routes_admin_actions_scripts_customer_portal_or_data_changes(self) -> None:
        for line in [
            "existing routes must not change in phase 5g",
            "existing admin actions must not change in phase 5g",
            "existing repair scripts must not change in phase 5g",
            "existing customer portal behavior must not change in phase 5g",
            "existing data records must not be migrated in phase 5g",
        ]:
            self.assertIn(line, self.doc_lower)

    def test_19_doc_includes_non_operational_guardrails(self) -> None:
        for line in [
            "phase 5g does not wire the validator into runtime routes",
            "phase 5g does not create apply mode",
            "phase 5g does not create repair scripts",
            "phase 5g does not touch live data",
            "phase 5g only defines canonical payload placement and tests the documentation",
        ]:
            self.assertIn(line, self.doc_lower)

    def test_20_if_payload_key_constants_exist_they_match_canonical_keys(self) -> None:
        expected = {
            "PAYLOAD_KEY_EVIDENCE_PACKET": "evidence_packet",
            "PAYLOAD_KEY_AUTHORIZATION_DECISION": "authorization_decision",
            "PAYLOAD_KEY_APPLY_TRANSITION": "apply_transition",
            "PAYLOAD_KEY_ROLLBACK_VERIFICATION": "rollback_verification",
            "PAYLOAD_KEY_STRUCTURED_OVERRIDE": "structured_override",
            "PAYLOAD_KEY_STRUCTURED_JUSTIFICATION": "structured_justification",
            "PAYLOAD_KEY_VALIDATOR_RESULT": "validator_result",
        }
        available = [name for name in expected if hasattr(self.module, name)]
        if not available:
            self.skipTest("Phase 5G payload key constants are optional and were not added")
        for name, value in expected.items():
            self.assertTrue(hasattr(self.module, name), f"Missing constant: {name}")
            self.assertEqual(getattr(self.module, name), value)

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
        self.assertNotIn("from ..scripts", self.source_lower)

    def test_22_validator_source_keeps_non_operational_guardrail_language(self) -> None:
        self.assertIn("does not execute repairs", self.source_lower)
        self.assertIn("does not write to the database", self.source_lower)
        self.assertIn("does not queue mint work", self.source_lower)
        self.assertIn("does not mutate certificates", self.source_lower)


if __name__ == "__main__":
    unittest.main()
