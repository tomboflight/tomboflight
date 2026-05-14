import ast
from copy import deepcopy
from importlib import import_module
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_readonly_helper.py"
MODULE_IMPORT = "backend.app.core.continuity_kernel_readonly_helper"
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6c_isolated_readonly_helper.md"
FLAG_NAME = "CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED"


class TestContinuityKernelPhase6CReadonlyHelper(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module_exists = MODULE_PATH.exists()
        cls.source_text = MODULE_PATH.read_text(encoding="utf-8") if cls.module_exists else ""
        cls.source_lower = cls.source_text.lower()
        cls.module = import_module(MODULE_IMPORT) if cls.module_exists else None
        cls.preview_module = import_module("backend.app.core.continuity_kernel_admin_preview") if cls.module_exists else None
        cls.doc_exists = DOC_PATH.exists()

    def _runtime_candidates(self, *patterns: str) -> list[Path]:
        candidates: list[Path] = []
        for pattern in patterns:
            candidates.extend(path for path in REPO_ROOT.glob(pattern) if path.is_file())
        return candidates

    def _assert_not_imported_under(self, paths: list[Path]) -> None:
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            self.assertNotIn("continuity_kernel_readonly_helper", text, msg=f"Unexpected helper import in {path}")

    def _enabled_env(self) -> dict:
        return {FLAG_NAME: "true"}

    def _sample_inputs(self) -> dict:
        return {
            "dry_run_source": {"dry_run_id": "dry-run-001", "risk_level": "medium", "idempotency_key": "idem-001"},
            "target_selector": {"target_type": "workspace", "target_id": "ws-001"},
            "actor_context": {"actor_user_id": "actor-1", "requested_by": "actor-1", "actor_role": "operations_admin"},
            "repair_category": "workspace_upload_readiness_preview",
            "before_snapshot": {"members": ["before"]},
            "proposed_after_snapshot": {"members": ["after"]},
            "diff_summary": "member role delta",
            "blocked_reasons": [],
            "rollback_plan": {"steps": ["restore before_snapshot_ref"], "secret_token": "DO_NOT_EXPOSE_ROLLBACK"},
            "structured_override": {
                "override_type": "manual",
                "approved_by": "admin-1",
                "approval_role": "SUPERADMIN",
                "reason_code": "URGENT",
                "reason_detail": "DO_NOT_EXPOSE_OVERRIDE_REASON_DETAIL",
                "target_type": "workspace",
                "target_id": "ws-001",
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
                "target_id": "ws-001",
                "repair_category": "workspace_upload_readiness_preview",
                "audit_context": {"internal": "DO_NOT_EXPOSE_AUDIT_CONTEXT"},
            },
        }

    def test_01_helper_module_exists(self) -> None:
        self.assertTrue(self.module_exists)

    def test_02_helper_module_imports_only_stdlib_and_approved_isolated_modules(self) -> None:
        tree = ast.parse(self.source_text)
        stdlib_names = set(getattr(sys, "stdlib_module_names", set()))
        approved_modules = {
            "backend.app.core.continuity_kernel_feature_flags",
            "backend.app.core.continuity_kernel_dry_run_adapter",
            "backend.app.core.continuity_kernel_validator",
            "backend.app.core.continuity_kernel_admin_preview",
            "backend.app.core.continuity_kernel_taxonomy",
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
                    self.assertTrue(
                        imported in approved_modules or imported.split(".")[0] in stdlib_names,
                        msg=f"Non-approved import found: {imported}",
                    )
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0)
                module_name = node.module or ""
                if module_name == "__future__":
                    continue
                self.assertTrue(
                    module_name in approved_modules or module_name.split(".")[0] in stdlib_names,
                    msg=f"Non-approved import found: {module_name}",
                )

    def test_03_helper_source_has_non_operational_guardrails(self) -> None:
        for expected in [
            "this module is isolated.",
            "this module is read-only.",
            "this module does not expose routes.",
            "this module does not execute repairs.",
            "this module does not approve apply.",
            "this module does not schedule apply.",
            "this module does not write to the database.",
            "this module does not queue mint work.",
            "this module does not mutate certificates.",
            "this module does not alter customer records.",
        ]:
            self.assertIn(expected, self.source_lower)

    def test_04_feature_flag_off_returns_enabled_false(self) -> None:
        response = self.module.build_readonly_preview_response(env={FLAG_NAME: "false"})
        self.assertIs(response["enabled"], False)

    def test_05_missing_feature_flag_returns_enabled_false(self) -> None:
        response = self.module.build_readonly_preview_response(env={})
        self.assertIs(response["enabled"], False)

    def test_06_invalid_feature_flag_returns_enabled_false(self) -> None:
        response = self.module.build_readonly_preview_response(env={FLAG_NAME: "invalid"})
        self.assertIs(response["enabled"], False)

    def test_07_feature_flag_off_returns_preview_none(self) -> None:
        response = self.module.build_readonly_preview_response(env={FLAG_NAME: "off"})
        self.assertIsNone(response["preview"])

    def test_08_feature_flag_off_returns_validator_result_none(self) -> None:
        response = self.module.build_readonly_preview_response(env={FLAG_NAME: "0"})
        self.assertIsNone(response["validator_result"])

    def test_09_feature_flag_off_returns_no_allowed_actions(self) -> None:
        response = self.module.build_readonly_preview_response(env={FLAG_NAME: "disabled"})
        self.assertEqual(response["allowed_actions"], [])

    def test_10_feature_flag_off_reason_codes_include_feature_flag_disabled(self) -> None:
        response = self.module.build_readonly_preview_response(env={FLAG_NAME: "false"})
        self.assertIn("FEATURE_FLAG_DISABLED", response["reason_codes"])

    def test_11_feature_flag_on_returns_enabled_true(self) -> None:
        response = self.module.build_readonly_preview_response(env=self._enabled_env(), **self._sample_inputs())
        self.assertIs(response["enabled"], True)

    def test_12_feature_flag_on_returns_preview_object(self) -> None:
        response = self.module.build_readonly_preview_response(env=self._enabled_env(), **self._sample_inputs())
        self.assertIsInstance(response["preview"], dict)

    def test_13_feature_flag_on_returns_validator_result(self) -> None:
        response = self.module.build_readonly_preview_response(env=self._enabled_env(), **self._sample_inputs())
        self.assertIsInstance(response["validator_result"], dict)

    def test_14_feature_flag_on_response_never_includes_prohibited_actions(self) -> None:
        response = self.module.build_readonly_preview_response(env=self._enabled_env(), **self._sample_inputs())
        prohibited = set(self.preview_module.PROHIBITED_ACTIONS)
        self.assertTrue(set(response["allowed_actions"]).isdisjoint(prohibited))
        self.assertTrue(set(response["preview"].get("allowed_actions", [])).isdisjoint(prohibited))

    def test_15_feature_flag_on_response_fails_closed_if_validator_fails(self) -> None:
        response = self.module.build_readonly_preview_response(
            env=self._enabled_env(),
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
        self.assertEqual(response["status"], "validation_failed")
        self.assertEqual(response["allowed_actions"], [])
        self.assertIn("VALIDATOR_FAILED_CLOSED", response["reason_codes"])

    def test_16_response_does_not_expose_full_rollback_plan(self) -> None:
        response = self.module.build_readonly_preview_response(env=self._enabled_env(), **self._sample_inputs())
        preview = response["preview"]
        self.assertIn("rollback_summary", preview)
        self.assertNotIn("rollback_plan", preview["rollback_summary"])
        self.assertNotIn("do_not_expose_rollback", str(response).lower())

    def test_17_response_does_not_expose_full_structured_override_reason_detail(self) -> None:
        response = self.module.build_readonly_preview_response(env=self._enabled_env(), **self._sample_inputs())
        self.assertNotIn("reason_detail", str(response["preview"].get("override_summary", {})).lower())
        self.assertNotIn("do_not_expose_override_reason_detail", str(response).lower())

    def test_18_response_does_not_expose_full_structured_justification_reason_detail(self) -> None:
        response = self.module.build_readonly_preview_response(env=self._enabled_env(), **self._sample_inputs())
        self.assertNotIn("reason_detail", str(response["preview"].get("justification_summary", {})).lower())
        self.assertNotIn("do_not_expose_justification_reason_detail", str(response).lower())

    def test_19_response_does_not_expose_full_audit_context(self) -> None:
        response = self.module.build_readonly_preview_response(env=self._enabled_env(), **self._sample_inputs())
        serialized = str(response).lower()
        self.assertNotIn("audit_context", serialized)
        self.assertNotIn("do_not_expose_audit_context", serialized)

    def test_20_helper_does_not_mutate_input_dictionaries(self) -> None:
        inputs = self._sample_inputs()
        baseline = deepcopy(inputs)
        _ = self.module.build_readonly_preview_response(env=self._enabled_env(), **inputs)
        self.assertEqual(inputs, baseline)

    def test_21_helper_module_is_not_imported_in_backend_app_routes(self) -> None:
        self._assert_not_imported_under(self._runtime_candidates("backend/app/routes/**/*.py", "backend/app/routes/*.py"))

    def test_22_helper_module_is_not_imported_in_backend_app_services(self) -> None:
        self._assert_not_imported_under(self._runtime_candidates("backend/app/services/**/*.py", "backend/app/services/*.py"))

    def test_23_helper_module_is_not_imported_in_backend_scripts(self) -> None:
        self._assert_not_imported_under(self._runtime_candidates("backend/scripts/**/*.py", "backend/scripts/*.py"))

    def test_24_helper_module_is_not_imported_in_backend_app_main_py(self) -> None:
        app_main = REPO_ROOT / "backend" / "app" / "main.py"
        self.assertTrue(app_main.exists())
        self._assert_not_imported_under([app_main])

    def test_25_no_database_read_write_tokens_appear_in_helper_source(self) -> None:
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
            "pymongo",
            "motor",
            "mongodb://",
        ]:
            self.assertNotIn(forbidden, self.source_lower)

    def test_26_no_apply_schedule_execute_rollback_behavior_appears_as_executable_action(self) -> None:
        for forbidden in [
            "approve_apply(",
            "schedule_apply(",
            "execute_apply(",
            "rollback_apply(",
            "run_repair_script(",
            "execute_repair(",
        ]:
            self.assertNotIn(forbidden, self.source_lower)


if __name__ == "__main__":
    unittest.main()
