from copy import deepcopy
from importlib import import_module
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6d_staging_payload_alignment.md"
ADAPTER_MODULE_IMPORT = "backend.app.core.continuity_kernel_dry_run_adapter"
HELPER_MODULE_IMPORT = "backend.app.core.continuity_kernel_readonly_helper"
PREVIEW_MODULE_IMPORT = "backend.app.core.continuity_kernel_admin_preview"
FLAG_NAME = "CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED"


class TestContinuityKernelPhase6DStagingPayloadAlignment(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = import_module(ADAPTER_MODULE_IMPORT)
        cls.helper = import_module(HELPER_MODULE_IMPORT)
        cls.preview_module = import_module(PREVIEW_MODULE_IMPORT)
        cls.adapter_source = (
            REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_dry_run_adapter.py"
        ).read_text(encoding="utf-8")
        cls.helper_source = (
            REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_readonly_helper.py"
        ).read_text(encoding="utf-8")
        cls.adapter_source_lower = cls.adapter_source.lower()
        cls.helper_source_lower = cls.helper_source.lower()

    def _runtime_candidates(self, *patterns: str) -> list[Path]:
        candidates: list[Path] = []
        for pattern in patterns:
            candidates.extend(path for path in REPO_ROOT.glob(pattern) if path.is_file())
        return candidates

    def _assert_no_kernel_runtime_imports(self, paths: list[Path]) -> None:
        kernel_module_tokens = [
            "continuity_kernel_readonly_helper",
            "continuity_kernel_dry_run_adapter",
            "continuity_kernel_validator",
            "continuity_kernel_admin_preview",
            "continuity_kernel_taxonomy",
        ]
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for token in kernel_module_tokens:
                self.assertNotIn(token, text, msg=f"Unexpected runtime kernel import token '{token}' in {path}")

    def _sample_inputs(self) -> dict:
        return {
            "dry_run_source": {
                "dry_run_id": "dry-run-6d-001",
                "risk_level": "medium",
                "idempotency_key": "idem-6d-001",
                "evidence_packet_id": "evidence-6d-001",
            },
            "target_selector": {"target_type": "workspace", "target_id": "ws-6d-001"},
            "actor_context": {"actor_user_id": "actor-6d", "requested_by": "actor-6d", "actor_role": "operations_admin"},
            "repair_category": "workspace_upload_readiness_preview",
            "before_snapshot": {"members": ["before"]},
            "proposed_after_snapshot": {"members": ["after"]},
            "diff_summary": "member role delta",
            "blocked_reasons": [],
            "rollback_plan": {"steps": ["restore before_snapshot_ref"]},
            "structured_override": {
                "override_type": "manual",
                "approved_by": "admin-1",
                "approval_role": "SUPERADMIN",
                "reason_code": "URGENT",
                "reason_detail": "DO_NOT_EXPOSE_OVERRIDE_REASON_DETAIL",
                "target_type": "workspace",
                "target_id": "ws-6d-001",
                "repair_category": "workspace_upload_readiness_preview",
                "risk_level": "medium",
                "audit_context": {"secret": "DO_NOT_EXPOSE_AUDIT_CONTEXT"},
            },
            "structured_justification": {
                "justification_type": "case_note",
                "provided_by": "admin-2",
                "reason_code": "POLICY",
                "reason_detail": "DO_NOT_EXPOSE_JUSTIFICATION_REASON_DETAIL",
                "related_field": "member_role",
                "target_type": "workspace",
                "target_id": "ws-6d-001",
                "repair_category": "workspace_upload_readiness_preview",
                "audit_context": {"internal": "DO_NOT_EXPOSE_AUDIT_CONTEXT"},
            },
        }

    def _build_payload(self) -> dict:
        i = self._sample_inputs()
        return self.adapter.build_staging_dry_run_payload(
            dry_run_source=i["dry_run_source"],
            target_selector=i["target_selector"],
            actor_context=i["actor_context"],
            repair_category=i["repair_category"],
            before_snapshot=i["before_snapshot"],
            proposed_after_snapshot=i["proposed_after_snapshot"],
            diff_summary=i["diff_summary"],
            blocked_reasons=i["blocked_reasons"],
            rollback_plan=i["rollback_plan"],
            structured_override=i["structured_override"],
            structured_justification=i["structured_justification"],
        )

    def test_01_phase6d_doc_exists(self) -> None:
        self.assertTrue(DOC_PATH.exists())

    def test_02_adapter_shares_evidence_packet_id_across_payload_parts(self) -> None:
        payload = self._build_payload()
        packet_id = payload["evidence_packet"]["evidence_packet_id"]
        self.assertEqual(packet_id, payload["apply_transition"]["evidence_packet_id"])
        self.assertEqual(packet_id, payload["rollback_verification"]["evidence_packet_id"])

    def test_03_adapter_shares_target_type_target_id_across_packet_authorization_rollback(self) -> None:
        payload = self._build_payload()
        packet = payload["evidence_packet"]
        authorization = payload["authorization_decision"]
        rollback = payload["rollback_verification"]
        self.assertEqual(packet["target_type"], authorization["target_type"])
        self.assertEqual(packet["target_id"], authorization["target_id"])
        self.assertEqual(packet["target_type"], rollback["target_type"])
        self.assertEqual(packet["target_id"], rollback["target_id"])

    def test_04_adapter_shares_repair_category_between_packet_and_authorization(self) -> None:
        payload = self._build_payload()
        self.assertEqual(
            payload["evidence_packet"]["repair_category"],
            payload["authorization_decision"]["repair_category"],
        )

    def test_05_adapter_idempotency_key_is_not_blank(self) -> None:
        payload = self._build_payload()
        self.assertTrue(str(payload["evidence_packet"]["idempotency_key"]).strip())

    def test_06_rollback_verification_references_before_snapshot_or_before_snapshot_ref(self) -> None:
        payload = self._build_payload()
        rollback_verification = payload["rollback_verification"]
        rollback_plan_text = str(rollback_verification.get("rollback_plan", "")).lower()
        before_snapshot_ref_text = str(rollback_verification.get("before_snapshot_ref", "")).lower()
        self.assertTrue(
            "before_snapshot" in rollback_plan_text
            or "before_snapshot_ref" in rollback_plan_text
            or "before_snapshot_ref" in before_snapshot_ref_text
        )

    def test_07_authorization_placeholder_remains_not_approved_by_default(self) -> None:
        payload = self._build_payload()
        authorization = payload["authorization_decision"]
        self.assertIs(authorization.get("approved"), False)
        self.assertIn("not_approved", str(authorization.get("decision", "")).lower())

    def test_08_apply_transition_transition_allowed_false_by_default(self) -> None:
        payload = self._build_payload()
        self.assertIs(payload["apply_transition"].get("transition_allowed"), False)

    def test_09_apply_transition_is_not_apply_executed(self) -> None:
        payload = self._build_payload()
        self.assertNotEqual(payload["apply_transition"].get("state"), "apply_executed")
        self.assertNotEqual(payload["apply_transition"].get("next_state"), "apply_executed")
        self.assertNotEqual(payload["apply_transition"].get("action"), "apply_executed")

    def test_10_readonly_helper_flag_off_remains_disabled(self) -> None:
        response = self.helper.build_readonly_preview_response(env={FLAG_NAME: "false"})
        self.assertIs(response.get("enabled"), False)

    def test_11_readonly_helper_flag_on_returns_preview_envelope(self) -> None:
        response = self.helper.build_readonly_preview_response(env={FLAG_NAME: "true"}, **self._sample_inputs())
        self.assertIs(response.get("enabled"), True)
        self.assertIsInstance(response.get("preview"), dict)

    def test_12_readonly_helper_flag_on_fails_closed_unless_approval_valid(self) -> None:
        response = self.helper.build_readonly_preview_response(
            env={FLAG_NAME: "true"},
            dry_run_source={},
            target_selector={},
            actor_context={},
            repair_category="",
            before_snapshot={},
            proposed_after_snapshot={},
            diff_summary="",
            blocked_reasons=[],
            rollback_plan={},
            structured_override={},
            structured_justification={},
        )
        self.assertEqual(response.get("status"), "validation_failed")
        self.assertIn("VALIDATOR_FAILED_CLOSED", response.get("reason_codes", []))

    def test_13_readonly_helper_allowed_actions_empty_when_validator_fails(self) -> None:
        response = self.helper.build_readonly_preview_response(
            env={FLAG_NAME: "true"},
            dry_run_source={},
            target_selector={},
            actor_context={},
            repair_category="",
            before_snapshot={},
            proposed_after_snapshot={},
            diff_summary="",
            blocked_reasons=[],
            rollback_plan={},
            structured_override={},
            structured_justification={},
        )
        self.assertEqual(response.get("allowed_actions"), [])
        self.assertEqual(response.get("preview", {}).get("allowed_actions"), [])

    def test_14_readonly_helper_never_returns_prohibited_actions(self) -> None:
        response = self.helper.build_readonly_preview_response(env={FLAG_NAME: "true"}, **self._sample_inputs())
        prohibited = set(self.preview_module.PROHIBITED_ACTIONS)
        self.assertTrue(set(response.get("allowed_actions", [])).isdisjoint(prohibited))
        self.assertTrue(set(response.get("preview", {}).get("allowed_actions", [])).isdisjoint(prohibited))

    def test_15_readonly_helper_does_not_expose_full_rollback_plan(self) -> None:
        response = self.helper.build_readonly_preview_response(env={FLAG_NAME: "true"}, **self._sample_inputs())
        rollback_summary = response.get("preview", {}).get("rollback_summary", {})
        self.assertNotIn("rollback_plan", rollback_summary)
        self.assertNotIn("do_not_expose_rollback", str(response).lower())

    def test_16_readonly_helper_does_not_expose_full_override_justification_audit_context(self) -> None:
        response = self.helper.build_readonly_preview_response(env={FLAG_NAME: "true"}, **self._sample_inputs())
        serialized = str(response).lower()
        self.assertNotIn("reason_detail", str(response.get("preview", {}).get("override_summary", {})).lower())
        self.assertNotIn("reason_detail", str(response.get("preview", {}).get("justification_summary", {})).lower())
        self.assertNotIn("audit_context", serialized)
        self.assertNotIn("do_not_expose_audit_context", serialized)

    def test_17_input_payloads_are_not_mutated(self) -> None:
        inputs = self._sample_inputs()
        baseline = deepcopy(inputs)
        _ = self.helper.build_readonly_preview_response(env={FLAG_NAME: "true"}, **inputs)
        self.assertEqual(inputs, baseline)

    def test_18_kernel_modules_not_imported_in_routes_services_scripts_main(self) -> None:
        runtime_paths = self._runtime_candidates(
            "backend/app/routes/**/*.py",
            "backend/app/routes/*.py",
            "backend/app/services/**/*.py",
            "backend/app/services/*.py",
            "backend/scripts/**/*.py",
            "backend/scripts/*.py",
        )
        runtime_paths.append(REPO_ROOT / "backend" / "app" / "main.py")
        self._assert_no_kernel_runtime_imports(runtime_paths)

    def test_19_no_database_read_write_tokens_in_changed_isolated_modules(self) -> None:
        forbidden_tokens = [
            "insert_one(",
            "update_one(",
            "delete_one(",
            "find_one(",
            "find(",
            "db[",
            "collection[",
            "session.commit(",
            "cursor.execute(",
            "pymongo",
            "motor",
            "mongodb://",
        ]
        for token in forbidden_tokens:
            self.assertNotIn(token, self.adapter_source_lower)
            self.assertNotIn(token, self.helper_source_lower)

    def test_20_no_apply_schedule_execute_rollback_actions_as_executable_behavior(self) -> None:
        forbidden_calls = [
            "approve_apply(",
            "schedule_apply(",
            "execute_apply(",
            "rollback_apply(",
            "run_repair_script(",
            "execute_repair(",
        ]
        for token in forbidden_calls:
            self.assertNotIn(token, self.adapter_source_lower)
            self.assertNotIn(token, self.helper_source_lower)


if __name__ == "__main__":
    unittest.main()
