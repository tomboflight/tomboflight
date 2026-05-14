from copy import deepcopy
from importlib import import_module
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_dry_run_adapter.py"
MODULE_IMPORT = "backend.app.core.continuity_kernel_dry_run_adapter"
VALIDATOR_IMPORT = "backend.app.core.continuity_kernel_validator"


class TestContinuityKernelPhase5JIsolatedDryRunAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module_exists = MODULE_PATH.exists()
        cls.source_text = MODULE_PATH.read_text(encoding="utf-8") if cls.module_exists else ""
        cls.source_lower = cls.source_text.lower()
        cls.module = import_module(MODULE_IMPORT) if cls.module_exists else None
        cls.validator_module = import_module(VALIDATOR_IMPORT)

    def _base_inputs(self) -> dict:
        return {
            "dry_run_source": {
                "dry_run_id": "dry-001",
                "risk_level": "low",
                "idempotency_key": "idem-001",
                "origin": "phase5j-contract-test",
            },
            "target_selector": {"target_type": "workspace", "target_id": "ws-001"},
            "actor_context": {
                "actor_user_id": "actor-001",
                "requested_by": "actor-001",
                "actor_role": "operations_admin",
            },
            "repair_category": "workspace_membership_repair",
            "before_snapshot": {"entitled": False},
            "proposed_after_snapshot": {"entitled": True},
            "diff_summary": {"changed": ["entitled"]},
            "blocked_reasons": ["staging_only_guardrail"],
            "rollback_plan": {"steps": ["restore before_snapshot_ref"]},
            "structured_override": {"override_id": "ovr-001"},
            "structured_justification": {"justification_id": "just-001"},
        }

    def _build_payload(self, **overrides):
        data = self._base_inputs()
        data.update(overrides)
        return self.module.build_staging_dry_run_payload(**data)

    def test_01_adapter_module_exists(self) -> None:
        self.assertTrue(self.module_exists)

    def test_02_adapter_module_imports_without_fastapi_mongo_pydantic_stripe_web3_dependencies(self) -> None:
        self.assertIsNotNone(self.module)
        for forbidden in ["fastapi", "pymongo", "motor", "bson", "pydantic", "stripe", "web3"]:
            self.assertNotIn(forbidden, self.source_lower)

    def test_03_source_text_says_staging_only_and_non_operational(self) -> None:
        self.assertIn("staging-only", self.source_lower)
        self.assertIn("does not execute repairs", self.source_lower)
        self.assertIn("does not write to the database", self.source_lower)
        self.assertIn("does not queue mint work", self.source_lower)
        self.assertIn("does not mutate certificates", self.source_lower)
        self.assertIn("does not alter customer records", self.source_lower)
        self.assertIn("does not call production services", self.source_lower)

    def test_04_build_staging_dry_run_payload_returns_all_canonical_top_level_keys(self) -> None:
        payload = self._build_payload()
        self.assertEqual(
            set(payload.keys()),
            {
                "evidence_packet",
                "authorization_decision",
                "apply_transition",
                "rollback_verification",
                "structured_override",
                "structured_justification",
                "validator_result",
            },
        )

    def test_05_evidence_packet_contains_required_validator_evidence_fields(self) -> None:
        payload = self._build_payload()
        evidence = payload["evidence_packet"]
        required = {
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
        }
        self.assertTrue(required.issubset(set(evidence.keys())))

    def test_06_authorization_decision_placeholder_is_not_approved(self) -> None:
        payload = self._build_payload()
        authorization = payload["authorization_decision"]
        self.assertFalse(authorization.get("approved"))
        self.assertNotIn(authorization.get("decision"), {"approve", "approved", "approved_for_apply"})

    def test_07_authorization_decision_placeholder_actor_role_is_not_superadmin_by_default(self) -> None:
        payload = self._build_payload(actor_context={"actor_user_id": "actor-001"})
        self.assertNotEqual(payload["authorization_decision"].get("actor_role"), "SUPERADMIN")

    def test_08_apply_transition_placeholder_is_not_apply_executed(self) -> None:
        payload = self._build_payload()
        transition = payload["apply_transition"]
        self.assertNotEqual(transition.get("next_state"), "apply_executed")

    def test_09_apply_transition_transition_allowed_is_false_by_default(self) -> None:
        payload = self._build_payload()
        self.assertIs(payload["apply_transition"].get("transition_allowed"), False)

    def test_10_validator_result_placeholder_passed_is_false_by_default(self) -> None:
        payload = self._build_payload()
        self.assertFalse(payload["validator_result"].get("passed"))

    def test_11_validator_result_reason_codes_include_validation_not_run(self) -> None:
        payload = self._build_payload()
        self.assertIn("VALIDATION_NOT_RUN", payload["validator_result"].get("reason_codes", []))

    def test_12_rollback_verification_placeholder_includes_rollback_plan(self) -> None:
        payload = self._build_payload()
        self.assertEqual(payload["rollback_verification"].get("rollback_plan"), {"steps": ["restore before_snapshot_ref"]})

    def test_13_adapter_does_not_mutate_input_dictionaries(self) -> None:
        base = self._base_inputs()
        before = deepcopy(base)
        _ = self.module.build_staging_dry_run_payload(**base)
        self.assertEqual(base, before)

    def test_14_missing_target_selector_fields_do_not_crash_and_produce_blank_placeholders(self) -> None:
        payload = self._build_payload(target_selector={})
        evidence = payload["evidence_packet"]
        self.assertEqual(evidence.get("target_type"), "")
        self.assertEqual(evidence.get("target_id"), "")

    def test_15_missing_actor_context_actor_user_id_does_not_crash_and_produces_blank_placeholder(self) -> None:
        payload = self._build_payload(actor_context={"requested_by": "requester"})
        evidence = payload["evidence_packet"]
        self.assertEqual(evidence.get("actor_user_id"), "")

    def test_16_missing_dry_run_id_does_not_crash_and_produces_safe_generated_dry_run_id(self) -> None:
        payload = self._build_payload(dry_run_source={"origin": "no-id"})
        dry_run_id = payload["evidence_packet"].get("dry_run_id")
        self.assertIsInstance(dry_run_id, str)
        self.assertNotEqual(dry_run_id.strip(), "")
        self.assertIn("dry-run-placeholder", dry_run_id)

    def test_17_structured_override_is_placed_only_at_top_level_structured_override(self) -> None:
        payload = self._build_payload(structured_override={"override_id": "ovr-top-only"})
        self.assertEqual(payload.get("structured_override"), {"override_id": "ovr-top-only"})
        self.assertNotIn("structured_override", payload["evidence_packet"])

    def test_18_structured_justification_is_placed_only_at_top_level_structured_justification(self) -> None:
        payload = self._build_payload(structured_justification={"justification_id": "just-top-only"})
        self.assertEqual(payload.get("structured_justification"), {"justification_id": "just-top-only"})
        self.assertNotIn("structured_justification", payload["evidence_packet"])

    def test_19_structured_override_is_not_inserted_into_audit_context(self) -> None:
        payload = self._build_payload(structured_override={"override_id": "ovr-audit-check"})
        audit_context_text = str(payload["evidence_packet"].get("audit_context", ""))
        self.assertNotIn("ovr-audit-check", audit_context_text)

    def test_20_structured_justification_is_not_inserted_into_audit_context(self) -> None:
        payload = self._build_payload(structured_justification={"justification_id": "just-audit-check"})
        audit_context_text = str(payload["evidence_packet"].get("audit_context", ""))
        self.assertNotIn("just-audit-check", audit_context_text)

    def test_21_adapter_module_is_not_imported_in_routes_services_scripts_main(self) -> None:
        adapter_module_name = "continuity_kernel_dry_run_adapter"
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
            self.assertNotIn(adapter_module_name, text, msg=f"Unexpected adapter import reference in {path}")

    def test_22_adapter_source_contains_no_database_read_write_language(self) -> None:
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

    def test_23_adapter_source_contains_no_repair_execution_language(self) -> None:
        for forbidden in ["execute_repair", "apply_repair", "run_repair_script", "repair_script("]:
            self.assertNotIn(forbidden, self.source_lower)

    def test_24_adapter_source_contains_no_mint_queueing_behavior(self) -> None:
        for forbidden in ["queue_mint_work(", "enqueue_mint(", "mint_queue", "publish_mint"]:
            self.assertNotIn(forbidden, self.source_lower)

    def test_25_adapter_output_can_be_passed_to_validator_and_fails_closed(self) -> None:
        payload = self._build_payload()
        result = self.validator_module.validate_apply_request(
            payload["evidence_packet"],
            payload["authorization_decision"],
            payload["apply_transition"],
            payload["rollback_verification"],
        )
        self.assertFalse(result.get("passed"))
        self.assertIn("AUTHORIZATION_NOT_APPROVED", result.get("reason_codes", []))


if __name__ == "__main__":
    unittest.main()
