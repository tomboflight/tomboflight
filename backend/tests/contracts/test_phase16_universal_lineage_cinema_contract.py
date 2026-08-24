from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]


class Phase16UniversalLineageCinemaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compiler = (
            REPO_ROOT
            / "backend/app/services/lineage_cinema_compiler.py"
        ).read_text(encoding="utf-8")
        cls.viewer = (
            REPO_ROOT
            / "backend/app/services/viewer_manifest_service.py"
        ).read_text(encoding="utf-8")
        cls.versions = (
            REPO_ROOT
            / "backend/app/services/cinematic_version_service.py"
        ).read_text(encoding="utf-8")
        cls.uploads = (
            REPO_ROOT / "backend/app/routes/uploads.py"
        ).read_text(encoding="utf-8")
        cls.frontend = (
            REPO_ROOT / "viewer/js/script.js"
        ).read_text(encoding="utf-8")
        cls.main = (REPO_ROOT / "backend/app/main.py").read_text(encoding="utf-8")

    def test_01_compiler_separates_content_states_from_repeatable_tour_steps(self):
        for marker in (
            "LINEAGE_CINEMA_COMPILER_VERSION",
            '"step_id": step_id',
            '"is_return": is_return',
            '"auto_advance_state_ids": tour_state_ids',
            '"complete": not missing_state_ids',
            '"tour_bounded": len(tour_steps) <= max_tour_steps',
        ):
            self.assertIn(marker, self.compiler)

    def test_02_viewer_compiles_the_full_approved_graph_without_preview_cap(self):
        for marker in (
            "compile_lineage_cinema(",
            'cinema_compilation.get("path_items")',
            'cinema_compilation.get("branch_options_by_state")',
            'manifest["tour_steps"]',
            '"navigation_mode": (',
            'cinema_compilation.get("validation")',
            '"eligible_state_count"',
            'else "sequence"',
        ):
            self.assertIn(marker, self.viewer)
        self.assertNotIn("states[:6]", self.viewer)

    def test_03_portrait_gate_requires_scan_consent_authority_and_master_approval(self):
        for marker in (
            'upload.get("scan_status")',
            'upload.get("quarantined")',
            'upload.get("approved_for_cinematic")',
            'upload.get("verification_status")',
            'upload.get("consent_status")',
            'upload.get("consent_attested")',
            'upload.get("authority_attested")',
            'upload.get("deletion_status")',
        ):
            self.assertIn(marker, self.viewer)

    def test_04_linked_portraits_require_root_access_graph_membership_and_provenance(self):
        for marker in (
            "_require_linked_cinematic_upload_access",
            'capabilities=("can_use_viewer",)',
            "build_linked_network(",
            'node.get("approved_photo_upload_id")',
            "Linked portrait provenance does not match",
        ):
            self.assertIn(marker, self.uploads)
        self.assertIn("viewer_project_id=", self.viewer)

    def test_05_private_versions_are_immutable_before_atomic_pointer_activation(self):
        insert_position = self.versions.index("versions.insert_one")
        pointer_position = self.versions.index("active.update_one")
        self.assertLess(insert_position, pointer_position)
        for marker in (
            "canonical_manifest_hash",
            '"version_key": version_key',
            '"manifest_snapshot": snapshot',
            'unique=True',
        ):
            self.assertIn(marker, self.versions)
        self.assertIn("ensure_cinematic_manifest_indexes()", self.main)

    def test_06_customer_slideshow_is_independent_from_paid_narration(self):
        for marker in (
            "function isAutoAdvanceEnabled()",
            'controls, "allow_auto_advance"',
            'return hasNarration ? "Narration: ON" : "Slideshow: ON"',
            "function isGraphNavigationMode()",
        ):
            self.assertIn(marker, self.frontend)


if __name__ == "__main__":
    unittest.main()
