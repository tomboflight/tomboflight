from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _glob(pattern: str) -> set[str]:
    return {_rel(p) for p in REPO_ROOT.glob(pattern) if p.is_file()}


class TestContinuityKernelArchitecture(unittest.TestCase):
    def test_continuity_kernel_docs_exist(self) -> None:
        required_docs = {
            "backend/docs/audits/tol_continuity_kernel_inventory.md",
            "backend/docs/architecture/tomb_of_light_continuity_kernel.md",
            "backend/docs/audits/tol_continuity_kernel_next_tasks.md",
        }
        missing = sorted(doc for doc in required_docs if not (REPO_ROOT / doc).is_file())
        self.assertFalse(missing, f"Missing required continuity docs: {missing}")

    def test_canonical_source_of_truth_files_exist(self) -> None:
        required_files = {
            "backend/app/core/package_catalog.py",
            "backend/app/core/package_mapping.py",
            "backend/app/core/package_type_catalog.py",
            "backend/app/core/role_catalog.py",
            "backend/app/services/entitlement_service.py",
            "backend/app/services/project_entitlement_service.py",
            "backend/app/services/workspace_access_service.py",
            "backend/app/services/viewer_manifest_service.py",
            "backend/app/services/public_manifest_service.py",
            "backend/app/services/issued_certificate_service.py",
            "backend/app/services/mint_policy_service.py",
            "backend/app/services/mint_record_service.py",
            "backend/app/services/audit_log_service.py",
        }
        missing = sorted(path for path in required_files if not (REPO_ROOT / path).is_file())
        self.assertFalse(missing, f"Missing canonical continuity files: {missing}")

    def test_no_duplicate_package_catalog_or_map_files_in_core(self) -> None:
        allowed = {
            "backend/app/core/package_catalog.py",
            "backend/app/core/package_mapping.py",
            "backend/app/core/package_type_catalog.py",
        }
        discovered = (
            _glob("backend/app/core/package*catalog*.py")
            | _glob("backend/app/core/package*map*.py")
            | _glob("backend/app/core/package*mapping*.py")
        )
        unexpected = sorted(path for path in discovered if path not in allowed)
        self.assertFalse(
            unexpected,
            (
                "Unexpected package catalog/map source-of-truth candidates found: "
                f"{unexpected}"
            ),
        )

    def test_no_duplicate_role_catalog_or_map_files_in_core(self) -> None:
        allowed = {"backend/app/core/role_catalog.py"}
        discovered = _glob("backend/app/core/role*catalog*.py") | _glob(
            "backend/app/core/role*map*.py"
        )
        unexpected = sorted(path for path in discovered if path not in allowed)
        self.assertFalse(
            unexpected,
            (
                "Unexpected role catalog/map source-of-truth candidates found: "
                f"{unexpected}"
            ),
        )

    def test_no_duplicate_entitlement_service_files(self) -> None:
        allowed = {
            "backend/app/services/entitlement_service.py",
            "backend/app/services/project_entitlement_service.py",
            "backend/app/services/package_provisioning_service.py",
        }
        discovered = _glob("backend/app/services/*entitlement*service.py") | _glob(
            "backend/app/services/package_provisioning_service.py"
        )
        unexpected = sorted(path for path in discovered if path not in allowed)
        self.assertFalse(
            unexpected,
            (
                "Unexpected entitlement service source-of-truth candidates found: "
                f"{unexpected}"
            ),
        )

    def test_no_duplicate_viewer_public_manifest_service_files(self) -> None:
        allowed = {
            "backend/app/services/viewer_manifest_service.py",
            "backend/app/services/public_manifest_service.py",
        }
        discovered = _glob("backend/app/services/*manifest*service.py")
        unexpected = sorted(path for path in discovered if path not in allowed)
        self.assertFalse(
            unexpected,
            (
                "Unexpected manifest service source-of-truth candidates found: "
                f"{unexpected}"
            ),
        )

    def test_viewer_and_public_manifest_services_are_separate_files(self) -> None:
        viewer = REPO_ROOT / "backend/app/services/viewer_manifest_service.py"
        public = REPO_ROOT / "backend/app/services/public_manifest_service.py"

        self.assertTrue(viewer.is_file(), "viewer_manifest_service.py must exist")
        self.assertTrue(public.is_file(), "public_manifest_service.py must exist")
        self.assertNotEqual(
            viewer.resolve(),
            public.resolve(),
            "Viewer and public manifest service paths must differ",
        )

    def test_repair_scripts_require_dry_run_or_apply_safety_pattern(self) -> None:
        scripts_dir = REPO_ROOT / "backend/scripts"
        script_files = sorted(scripts_dir.glob("*.py"))
        self.assertTrue(script_files, "Expected at least one backend script to inspect")

        write_signal = re.compile(
            r"\b(update|insert|delete|replace|write|save|upsert)\s*\(|\b(apply|repair|enforce|backfill|migrate)\b",
            re.IGNORECASE,
        )
        safety_pattern = re.compile(
            r"(--dry-run|--dryrun|dry_run|dry-run|--apply|apply_mode|\bapply\s*=|\bAPPLY\b)",
            re.IGNORECASE,
        )

        violations: list[str] = []
        for script in script_files:
            text = script.read_text(encoding="utf-8")
            if write_signal.search(text) and not safety_pattern.search(text):
                violations.append(_rel(script))

        self.assertFalse(
            violations,
            (
                "Write/apply-capable scripts must expose dry-run/apply safety controls. "
                f"Missing safety pattern in: {violations}"
            ),
        )

    def test_architecture_doc_contains_key_kernel_sections(self) -> None:
        architecture_doc = (
            REPO_ROOT / "backend/docs/architecture/tomb_of_light_continuity_kernel.md"
        )
        text = architecture_doc.read_text(encoding="utf-8")

        required_sections = [
            "Identity Resolver",
            "Entitlement Graph Resolver",
            "Workspace Access Resolver",
            "Viewer Manifest Compiler",
            "Readiness Gate Matrix",
            "Mint Readiness Controller",
            "Officer Policy Layer",
            "Self-Healing Repair Engine",
            "Audit Timeline",
        ]

        missing = [section for section in required_sections if section not in text]
        self.assertFalse(
            missing, f"Architecture doc is missing kernel sections: {missing}"
        )
