from importlib import import_module
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase5i_staging_dry_run_adapter.md"
MODULE_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_dry_run_adapter.py"
MODULE_IMPORT = "backend.app.core.continuity_kernel_dry_run_adapter"


class TestContinuityKernelPhase5IStagingDryRunAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if DOC_PATH.exists() else ""
        cls.doc_lower = cls.doc_text.lower()
        cls.module_exists = MODULE_PATH.exists()
        cls.module_text = MODULE_PATH.read_text(encoding="utf-8") if cls.module_exists else ""
        cls.module_lower = cls.module_text.lower()

    def test_01_phase5i_doc_exists(self) -> None:
        self.assertTrue(DOC_PATH.exists())

    def test_02_doc_says_adapter_never_executes_repairs(self) -> None:
        self.assertIn("never execute repairs", self.doc_lower)

    def test_03_doc_says_adapter_never_writes_to_database(self) -> None:
        self.assertIn("never write to database", self.doc_lower)

    def test_04_doc_says_adapter_never_queues_mint_work(self) -> None:
        self.assertIn("never queue mint work", self.doc_lower)

    def test_05_doc_says_adapter_never_mutates_certificates(self) -> None:
        self.assertIn("never mutate certificates", self.doc_lower)

    def test_06_doc_says_adapter_never_alters_customer_records(self) -> None:
        self.assertIn("never alter customer records", self.doc_lower)

    def test_07_doc_lists_all_adapter_inputs(self) -> None:
        for value in [
            "dry_run_source",
            "target_selector",
            "actor_context",
            "repair_category",
            "before_snapshot",
            "proposed_after_snapshot",
            "diff_summary",
            "blocked_reasons",
            "rollback_plan",
            "structured_override",
            "structured_justification",
        ]:
            self.assertIn(value, self.doc_text)

    def test_08_doc_lists_all_adapter_outputs(self) -> None:
        for value in [
            "evidence_packet",
            "authorization_decision",
            "apply_transition",
            "rollback_verification",
            "validator_result",
        ]:
            self.assertIn(value, self.doc_text)

    def test_09_doc_states_output_is_not_approval(self) -> None:
        self.assertIn("adapter output is not approval", self.doc_lower)

    def test_10_doc_states_output_is_not_apply_authorization(self) -> None:
        self.assertIn("adapter output is not apply authorization", self.doc_lower)

    def test_11_doc_states_output_is_not_repair_script(self) -> None:
        self.assertIn("adapter output is not a repair script", self.doc_lower)

    def test_12_doc_states_output_cannot_queue_mint_work(self) -> None:
        self.assertIn("adapter output cannot be used to queue mint work", self.doc_lower)

    def test_13_doc_states_output_cannot_mutate_issued_certificates(self) -> None:
        self.assertIn("adapter output cannot be used to mutate issued certificates", self.doc_lower)

    def test_14_doc_includes_producer_migration_boundaries(self) -> None:
        for value in [
            "dry_run_engine may produce dry_run_source",
            "adapter may assemble evidence_packet only from supplied in-memory inputs",
            "authorization_policy must produce authorization_decision separately",
            "state_machine must produce apply_transition separately",
            "rollback_planner must produce rollback_verification separately",
            "officer_review must produce structured_override separately",
            "reviewer_notes must produce structured_justification separately",
            "continuity_kernel_validator produces validator_result",
        ]:
            self.assertIn(value, self.doc_lower)

    def test_15_doc_includes_non_operational_guardrails(self) -> None:
        for value in [
            "phase 5i does not wire the adapter into runtime routes",
            "phase 5i does not create apply mode",
            "phase 5i does not create repair scripts",
            "phase 5i does not touch live data",
            "phase 5i only defines staging-only adapter contracts and tests",
        ]:
            self.assertIn(value, self.doc_lower)

    def test_16_optional_module_is_isolated_and_staging_only(self) -> None:
        if not self.module_exists:
            self.skipTest("Optional Phase 5I dry-run adapter module was not added")

        self.assertIn("staging-only", self.module_lower)
        self.assertIn("non-operational", self.module_lower)
        self.assertNotIn("fastapi", self.module_lower)
        self.assertNotIn("pydantic", self.module_lower)
        self.assertNotIn("pymongo", self.module_lower)
        self.assertNotIn("motor", self.module_lower)
        self.assertNotIn("mongo", self.module_lower)
        self.assertNotIn("backend.app.routes", self.module_lower)
        self.assertNotIn("backend.app.services", self.module_lower)
        self.assertNotIn("backend.scripts", self.module_lower)
        self.assertNotIn("from ..routes", self.module_lower)
        self.assertNotIn("from ..services", self.module_lower)
        self.assertNotIn("from ..scripts", self.module_lower)

    def test_17_optional_module_build_staging_payload_has_canonical_keys_and_safe_placeholders(self) -> None:
        if not self.module_exists:
            self.skipTest("Optional Phase 5I dry-run adapter module was not added")

        module = import_module(MODULE_IMPORT)
        payload = module.build_staging_dry_run_payload(
            dry_run_source={"origin": "test"},
            target_selector={"scope": "test"},
            actor_context={"actor": "test"},
            repair_category="test",
            before_snapshot={"before": True},
            proposed_after_snapshot={"after": False},
            diff_summary={"changed": 1},
            blocked_reasons=["staging_only"],
            rollback_plan={"steps": []},
            structured_override={"present": False},
            structured_justification={"note": "placeholder"},
        )

        self.assertEqual(
            set(payload.keys()),
            {
                "evidence_packet",
                "authorization_decision",
                "apply_transition",
                "rollback_verification",
                "validator_result",
            },
        )
        self.assertFalse(payload["authorization_decision"].get("approved", False))
        self.assertNotEqual(payload["apply_transition"].get("state"), "apply_executed")
        self.assertIn("output", str(payload["validator_result"]).lower())
        self.assertIn("placeholder", str(payload["validator_result"]).lower())


if __name__ == "__main__":
    unittest.main()
