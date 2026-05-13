from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend/docs/repair/continuity_kernel_phase4_dry_run_repair_plans.md"


class TestContinuityKernelPhase4RepairPlans(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8")
        cls.doc_lower = cls.doc_text.lower()

    def test_phase4_repair_plan_doc_exists(self) -> None:
        self.assertTrue(DOC_PATH.is_file(), "Phase 4 dry-run repair plan doc must exist.")

    def test_doc_states_dry_run_is_default(self) -> None:
        self.assertRegex(self.doc_lower, r"dry-run\s+is\s+the\s+default")

    def test_doc_mentions_future_apply_as_gated_approved_behavior(self) -> None:
        self.assertRegex(self.doc_text, r"future\s+`--apply`", re.IGNORECASE)
        self.assertIn("officer-policy approval", self.doc_lower)

    def test_doc_includes_rollback_notes(self) -> None:
        self.assertIn("rollback notes", self.doc_lower)

    def test_doc_includes_idempotency_notes(self) -> None:
        self.assertIn("idempotency notes", self.doc_lower)

    def test_doc_includes_audit_actor_action_target_context_language(self) -> None:
        self.assertRegex(self.doc_lower, r"audit\s+actor/action/target/context")

    def test_doc_includes_officer_policy_approval_language(self) -> None:
        self.assertIn("officer-policy approval", self.doc_lower)

    def test_doc_includes_all_seven_repair_categories(self) -> None:
        required_categories = [
            "missing entitlement repair plan",
            "package/lane normalization repair plan",
            "workspace/co-owner membership repair plan",
            "viewer manifest readiness repair plan",
            "certificate issuance consistency repair plan",
            "mint readiness repair plan",
            "admin repair safety plan",
        ]
        missing = [token for token in required_categories if token not in self.doc_lower]
        self.assertFalse(missing, f"Missing repair plan categories: {missing}")

    def test_doc_says_not_to_mutate_immutable_issued_certificates(self) -> None:
        self.assertIn("do not mutate immutable issued certificates", self.doc_lower)

    def test_doc_says_not_to_queue_mint_work_directly_from_repair_plan(self) -> None:
        self.assertIn("do not queue mint work directly from a repair plan", self.doc_lower)

    def test_scripts_with_write_signals_still_require_dry_run_or_apply_patterns(self) -> None:
        scripts_dir = REPO_ROOT / "backend/scripts"
        script_files = sorted(scripts_dir.glob("*.py"))
        self.assertTrue(script_files, "Expected backend/scripts Python files for policy checks.")

        write_signal = re.compile(
            r"\b(update|insert|delete|replace|write|save|upsert)\s*\(|\b(apply|repair|enforce|backfill|migrate)\b",
            re.IGNORECASE,
        )
        safety_pattern = re.compile(
            r"(--dry-run|--dryrun|dry_run|dry-run|--apply|apply_mode|\bapply\s*=|\bAPPLY\b)",
            re.IGNORECASE,
        )

        violations = []
        for script in script_files:
            text = script.read_text(encoding="utf-8")
            if write_signal.search(text) and not safety_pattern.search(text):
                violations.append(script.relative_to(REPO_ROOT).as_posix())

        self.assertFalse(
            violations,
            (
                "Write/apply-capable scripts must expose dry-run/apply safety controls. "
                f"Missing safety pattern in: {violations}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
