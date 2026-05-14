from copy import deepcopy
from importlib import import_module
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6f_test_fixture_guardrails.md"
FIXTURE_MODULE_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_test_fixtures.py"
HELPER_MODULE_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_readonly_helper.py"
FIXTURE_MODULE_IMPORT = "backend.app.core.continuity_kernel_test_fixtures"
HELPER_MODULE_IMPORT = "backend.app.core.continuity_kernel_readonly_helper"
PREVIEW_MODULE_IMPORT = "backend.app.core.continuity_kernel_admin_preview"
FLAG_NAME = "CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED"


class TestContinuityKernelPhase6FTestFixtureGuardrails(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_exists = DOC_PATH.exists()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if cls.doc_exists else ""
        cls.doc_lower = cls.doc_text.lower()

        cls.fixture_source = FIXTURE_MODULE_PATH.read_text(encoding="utf-8")
        cls.fixture_source_lower = cls.fixture_source.lower()
        cls.helper_source = HELPER_MODULE_PATH.read_text(encoding="utf-8")
        cls.helper_source_lower = cls.helper_source.lower()

        cls.fixture_module = import_module(FIXTURE_MODULE_IMPORT)
        cls.helper_module = import_module(HELPER_MODULE_IMPORT)
        cls.preview_module = import_module(PREVIEW_MODULE_IMPORT)

    def _runtime_candidates(self, *patterns: str) -> list[Path]:
        candidates: list[Path] = []
        for pattern in patterns:
            candidates.extend(path for path in REPO_ROOT.glob(pattern) if path.is_file())
        return candidates

    def _assert_not_imported_under(self, token: str, paths: list[Path]) -> None:
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            self.assertNotIn(token, text, msg=f"Unexpected import token '{token}' in {path}")

    def _fixture(self) -> dict:
        return self.fixture_module.build_valid_workspace_membership_approval_fixture()

    def test_01_phase6f_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_approval_fixture_payload_is_test_only(self) -> None:
        self.assertIn("approval_fixture_payload is test-only", self.doc_lower)

    def test_03_doc_says_explicit_test_context_true_or_equivalent_is_required(self) -> None:
        self.assertIn(
            "approval_fixture_payload must require explicit test_context=true or equivalent isolated test marker",
            self.doc_lower,
        )

    def test_04_doc_says_fixture_payloads_are_not_production_approvals(self) -> None:
        self.assertIn("fixture payloads are not production approvals", self.doc_lower)

    def test_05_doc_says_fixture_payloads_are_not_admin_approvals(self) -> None:
        self.assertIn("fixture payloads are not admin approvals", self.doc_lower)

    def test_06_doc_says_fixture_payloads_are_not_database_records(self) -> None:
        self.assertIn("fixture payloads are not database records", self.doc_lower)

    def test_07_doc_says_fixture_payloads_are_not_apply_authorization(self) -> None:
        self.assertIn("fixture payloads are not apply authorization", self.doc_lower)

    def test_08_doc_says_fixture_payloads_must_not_be_accepted_from_user_input(self) -> None:
        self.assertIn("fixture payloads must not be accepted from user input", self.doc_lower)

    def test_09_helper_with_approval_fixture_payload_and_no_test_context_fails_closed(self) -> None:
        response = self.helper_module.build_readonly_preview_response(
            env={FLAG_NAME: "true"},
            approval_fixture_payload=deepcopy(self._fixture()),
        )
        self.assertTrue(response.get("enabled"))
        self.assertIn(response.get("status"), {"blocked", "invalid_payload"})
        self.assertIsNone(response.get("preview"))
        self.assertEqual(response.get("allowed_actions"), [])

    def test_10_helper_with_approval_fixture_payload_and_test_context_false_fails_closed(self) -> None:
        response = self.helper_module.build_readonly_preview_response(
            env={FLAG_NAME: "true"},
            approval_fixture_payload=deepcopy(self._fixture()),
            test_context=False,
        )
        self.assertTrue(response.get("enabled"))
        self.assertIn(response.get("status"), {"blocked", "invalid_payload"})
        self.assertIsNone(response.get("preview"))
        self.assertEqual(response.get("allowed_actions"), [])

    def test_11_helper_with_fixture_and_test_context_true_but_feature_flag_off_returns_disabled(self) -> None:
        response = self.helper_module.build_readonly_preview_response(
            env={FLAG_NAME: "false"},
            approval_fixture_payload=deepcopy(self._fixture()),
            test_context=True,
        )
        self.assertIs(response.get("enabled"), False)
        self.assertEqual(response.get("status"), "disabled")
        self.assertIsNone(response.get("preview"))
        self.assertIsNone(response.get("validator_result"))
        self.assertEqual(response.get("allowed_actions"), [])
        self.assertIn("FEATURE_FLAG_DISABLED", response.get("reason_codes", []))

    def test_12_helper_with_fixture_and_test_context_true_and_feature_flag_on_returns_preview_path(self) -> None:
        response = self.helper_module.build_readonly_preview_response(
            env={FLAG_NAME: "true"},
            approval_fixture_payload=deepcopy(self._fixture()),
            test_context=True,
        )
        self.assertIs(response.get("enabled"), True)
        self.assertIsInstance(response.get("preview"), dict)
        self.assertIn(response.get("status"), {"preview_ready", "blocked", "review_required"})

    def test_13_helper_fail_closed_response_includes_test_context_required_when_fixture_lacks_test_marker(self) -> None:
        response = self.helper_module.build_readonly_preview_response(
            env={FLAG_NAME: "true"},
            approval_fixture_payload=deepcopy(self._fixture()),
        )
        self.assertIn("TEST_CONTEXT_REQUIRED", response.get("reason_codes", []))

    def test_14_helper_fixture_path_never_returns_prohibited_actions(self) -> None:
        response = self.helper_module.build_readonly_preview_response(
            env={FLAG_NAME: "true"},
            approval_fixture_payload=deepcopy(self._fixture()),
            test_context=True,
        )
        prohibited = set(self.preview_module.PROHIBITED_ACTIONS)
        self.assertTrue(set(response.get("allowed_actions", [])).isdisjoint(prohibited))
        self.assertTrue(set(response.get("preview", {}).get("allowed_actions", [])).isdisjoint(prohibited))

    def test_15_fixture_module_docstring_mentions_test_context_true(self) -> None:
        self.assertIn("test_context=true", self.fixture_source_lower)

    def test_16_fixture_module_is_not_imported_in_routes_services_scripts_main(self) -> None:
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

    def test_17_readonly_helper_is_not_imported_in_routes_services_scripts_main(self) -> None:
        runtime_paths = self._runtime_candidates(
            "backend/app/routes/**/*.py",
            "backend/app/routes/*.py",
            "backend/app/services/**/*.py",
            "backend/app/services/*.py",
            "backend/scripts/**/*.py",
            "backend/scripts/*.py",
        )
        runtime_paths.append(REPO_ROOT / "backend" / "app" / "main.py")
        self._assert_not_imported_under("continuity_kernel_readonly_helper", runtime_paths)

    def test_18_no_database_read_write_tokens_appear_in_changed_isolated_modules(self) -> None:
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

    def test_19_no_apply_schedule_execute_rollback_behavior_appears_as_executable_mutation_behavior(self) -> None:
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

    def test_20_full_architecture_and_contract_tests_still_pass(self) -> None:
        self.assertTrue((REPO_ROOT / "backend" / "tests" / "architecture").exists())
        self.assertTrue((REPO_ROOT / "backend" / "tests" / "contracts").exists())


if __name__ == "__main__":
    unittest.main()
