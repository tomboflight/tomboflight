from copy import deepcopy
from importlib import import_module
from pathlib import Path
import ast
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6e_valid_approval_fixtures.md"
FIXTURE_MODULE_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_test_fixtures.py"
FIXTURE_MODULE_IMPORT = "backend.app.core.continuity_kernel_test_fixtures"
HELPER_MODULE_IMPORT = "backend.app.core.continuity_kernel_readonly_helper"
PREVIEW_MODULE_IMPORT = "backend.app.core.continuity_kernel_admin_preview"
VALIDATOR_MODULE_IMPORT = "backend.app.core.continuity_kernel_validator"
FLAG_NAME = "CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED"


class TestContinuityKernelPhase6EValidApprovalFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_exists = DOC_PATH.exists()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if cls.doc_exists else ""
        cls.doc_lower = cls.doc_text.lower()

        cls.fixture_exists = FIXTURE_MODULE_PATH.exists()
        cls.fixture_source = FIXTURE_MODULE_PATH.read_text(encoding="utf-8") if cls.fixture_exists else ""
        cls.fixture_source_lower = cls.fixture_source.lower()

        cls.helper_source_path = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_readonly_helper.py"
        cls.helper_source = cls.helper_source_path.read_text(encoding="utf-8")
        cls.helper_source_lower = cls.helper_source.lower()

        cls.fixture_module = import_module(FIXTURE_MODULE_IMPORT) if cls.fixture_exists else None
        cls.helper_module = import_module(HELPER_MODULE_IMPORT)
        cls.preview_module = import_module(PREVIEW_MODULE_IMPORT)
        cls.validator_module = import_module(VALIDATOR_MODULE_IMPORT)

    def _runtime_candidates(self, *patterns: str) -> list[Path]:
        candidates: list[Path] = []
        for pattern in patterns:
            candidates.extend(path for path in REPO_ROOT.glob(pattern) if path.is_file())
        return candidates

    def _assert_not_imported_under(self, token: str, paths: list[Path]) -> None:
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            self.assertNotIn(token, text, msg=f"Unexpected import token '{token}' in {path}")

    def _fixtures(self) -> list[dict]:
        if not self.fixture_exists:
            self.skipTest("Optional Phase 6E fixture module was not added")

        return [
            self.fixture_module.build_valid_workspace_membership_approval_fixture(),
            self.fixture_module.build_valid_viewer_readiness_approval_fixture(),
            self.fixture_module.build_valid_billing_order_approval_fixture(),
        ]

    def test_01_phase6e_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_fixtures_are_in_memory_only(self) -> None:
        self.assertIn("fixtures are in-memory only", self.doc_lower)

    def test_03_doc_says_fixtures_are_not_production_approvals(self) -> None:
        self.assertIn("fixtures are not production approvals", self.doc_lower)

    def test_04_doc_says_fixtures_are_not_admin_approvals(self) -> None:
        self.assertIn("fixtures are not admin approvals", self.doc_lower)

    def test_05_doc_says_fixtures_are_not_database_records(self) -> None:
        self.assertIn("fixtures are not database records", self.doc_lower)

    def test_06_doc_says_fixtures_are_not_apply_authorization(self) -> None:
        self.assertIn("fixtures are not apply authorization", self.doc_lower)

    def test_07_doc_says_fixtures_must_not_be_accepted_from_user_input(self) -> None:
        self.assertIn("fixtures must not be accepted from user input", self.doc_lower)

    def test_08_doc_lists_required_fixture_components(self) -> None:
        for value in [
            "evidence_packet",
            "authorization_decision",
            "apply_transition",
            "rollback_verification",
            "structured_override",
            "structured_justification",
        ]:
            self.assertIn(value, self.doc_text)

    def test_09_doc_lists_valid_approval_fixture_rules(self) -> None:
        for value in [
            "authorization_decision may be approved only in isolated tests",
            "actor_role must be canonical and allowed for repair_category",
            "approved_by must match authorization actor",
            "apply_transition must use allowed transition only",
            "rollback_verification must match target and evidence_packet_id",
            "idempotency_key must be non-blank",
            "audit_context must exist",
            "no prohibited actions may appear",
        ]:
            self.assertIn(value, self.doc_lower)

    def test_10_doc_lists_prohibited_fixture_behavior(self) -> None:
        for value in [
            "fixtures must not create apply mode",
            "fixtures must not create repair scripts",
            "fixtures must not mutate data",
            "fixtures must not queue mint work",
            "fixtures must not mutate certificates",
            "fixtures must not delete customer records",
            "fixtures must not bypass validator",
            "fixtures must not bypass audit",
        ]:
            self.assertIn(value, self.doc_lower)

    def test_11_doc_includes_non_operational_guardrails(self) -> None:
        for value in [
            "phase 6e does not wire runtime routes.",
            "phase 6e does not wire services.",
            "phase 6e does not create admin ui actions.",
            "phase 6e does not create apply mode.",
            "phase 6e does not create repair scripts.",
            "phase 6e does not touch live data.",
        ]:
            self.assertIn(value, self.doc_lower)

    def test_12_optional_fixture_module_imports_allow_stdlib_and_approved_isolated_core_modules_only(self) -> None:
        if not self.fixture_exists:
            self.skipTest("Optional Phase 6E fixture module was not added")

        stdlib_names = set(getattr(sys, "stdlib_module_names", set()))
        approved_modules = {
            "backend.app.core.continuity_kernel_validator",
            "backend.app.core.continuity_kernel_readonly_helper",
            "backend.app.core.continuity_kernel_admin_preview",
            "backend.app.core.continuity_kernel_dry_run_adapter",
            "backend.app.core.continuity_kernel_taxonomy",
            "backend.app.core.continuity_kernel_test_fixtures",
        }
        tree = ast.parse(self.fixture_source)

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

    def test_13_optional_fixture_module_fixtures_validate_successfully_with_validate_apply_request(self) -> None:
        for fixture in self._fixtures():
            result = self.validator_module.validate_apply_request(
                packet=deepcopy(fixture["evidence_packet"]),
                authorization=deepcopy(fixture["authorization_decision"]),
                transition=deepcopy(fixture["apply_transition"]),
                rollback=deepcopy(fixture["rollback_verification"]),
            )
            self.assertTrue(result.get("passed"), msg=f"Validation failed: {result}")

    def test_14_optional_fixture_module_helper_flag_on_valid_fixture_returns_preview_ready_or_non_error_preview_status(self) -> None:
        for fixture in self._fixtures():
            response = self.helper_module.build_readonly_preview_response(
                env={FLAG_NAME: "true"},
                approval_fixture_payload=deepcopy(fixture),
                test_context=True,
            )
            self.assertTrue(response.get("enabled"))
            self.assertIsInstance(response.get("preview"), dict)
            self.assertIn(response.get("status"), {"preview_ready", "blocked", "review_required"})

    def test_15_optional_fixture_module_allowed_actions_contain_only_read_only_actions(self) -> None:
        allowed_set = set(self.preview_module.ALLOWED_READ_ONLY_ACTIONS)
        for fixture in self._fixtures():
            response = self.helper_module.build_readonly_preview_response(
                env={FLAG_NAME: "true"},
                approval_fixture_payload=deepcopy(fixture),
                test_context=True,
            )
            actions = response.get("allowed_actions", [])
            preview_actions = response.get("preview", {}).get("allowed_actions", [])
            self.assertTrue(set(actions).issubset(allowed_set))
            self.assertTrue(set(preview_actions).issubset(allowed_set))

    def test_16_optional_fixture_module_no_prohibited_actions_appear(self) -> None:
        prohibited = set(self.preview_module.PROHIBITED_ACTIONS)
        for fixture in self._fixtures():
            response = self.helper_module.build_readonly_preview_response(
                env={FLAG_NAME: "true"},
                approval_fixture_payload=deepcopy(fixture),
                test_context=True,
            )
            self.assertTrue(set(response.get("allowed_actions", [])).isdisjoint(prohibited))
            self.assertTrue(set(response.get("preview", {}).get("allowed_actions", [])).isdisjoint(prohibited))

    def test_17_optional_fixture_module_fixtures_do_not_mutate_input_payloads(self) -> None:
        for fixture in self._fixtures():
            baseline = deepcopy(fixture)
            _ = self.helper_module.build_readonly_preview_response(
                env={FLAG_NAME: "true"},
                approval_fixture_payload=fixture,
                test_context=True,
            )
            self.assertEqual(fixture, baseline)

    def test_18_optional_fixture_module_is_not_imported_in_routes_services_scripts_main(self) -> None:
        runtime_paths = self._runtime_candidates(
            "backend/app/routes/**/*.py",
            "backend/app/routes/*.py",
            "backend/app/services/**/*.py",
            "backend/app/services/*.py",
            "backend/scripts/**/*.py",
            "backend/scripts/*.py",
        )
        runtime_paths.append(REPO_ROOT / "backend" / "app" / "main.py")
        self._assert_not_imported_under("continuity_kernel_test_fixtures", runtime_paths)

    def test_19_kernel_modules_are_still_not_imported_in_routes_services_scripts_main(self) -> None:
        runtime_paths = self._runtime_candidates(
            "backend/app/routes/**/*.py",
            "backend/app/routes/*.py",
            "backend/app/services/**/*.py",
            "backend/app/services/*.py",
            "backend/scripts/**/*.py",
            "backend/scripts/*.py",
        )
        runtime_paths.append(REPO_ROOT / "backend" / "app" / "main.py")

        for token in [
            "continuity_kernel_readonly_helper",
            "continuity_kernel_dry_run_adapter",
            "continuity_kernel_validator",
            "continuity_kernel_admin_preview",
            "continuity_kernel_taxonomy",
        ]:
            self._assert_not_imported_under(token, runtime_paths)

    def test_20_no_database_read_write_tokens_appear_in_fixture_module_or_changed_isolated_modules(self) -> None:
        for source in [self.fixture_source_lower, self.helper_source_lower]:
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
                self.assertNotIn(forbidden, source)

    def test_21_no_apply_schedule_execute_rollback_behavior_appears_as_executable_mutation_behavior(self) -> None:
        for source in [self.fixture_source_lower, self.helper_source_lower]:
            for forbidden in [
                "approve_apply(",
                "schedule_apply(",
                "execute_apply(",
                "rollback_apply(",
                "run_repair_script(",
                "execute_repair(",
            ]:
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
