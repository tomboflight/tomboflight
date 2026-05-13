from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]


class TestContinuityKernelPhase3Contracts(unittest.TestCase):
    def _file(self, relative_path: str) -> Path:
        return REPO_ROOT / relative_path

    def _read(self, relative_path: str) -> str:
        return self._file(relative_path).read_text(encoding="utf-8")

    def _assert_exists(self, relative_paths: set[str], context: str) -> None:
        missing = sorted(path for path in relative_paths if not self._file(path).is_file())
        self.assertFalse(missing, f"Missing {context} files: {missing}")

    def test_workspace_access_contract_files_and_route_compatibility(self) -> None:
        self._assert_exists(
            {
                "backend/app/services/workspace_access_service.py",
                "backend/app/services/access_context_service.py",
                "backend/app/services/project_membership_service.py",
                "backend/app/routes/workspace_access.py",
                "backend/app/routes/users.py",
            },
            "workspace/access contract",
        )

        users_route = self._read("backend/app/routes/users.py")
        self.assertRegex(users_route, r'@router\.get\("/me/workspace-context"\)')
        self.assertRegex(users_route, r'@router\.get\("/me/access-context"\)')
        self.assertRegex(
            users_route,
            re.compile(
                r"def\s+get_my_access_context\(.*?return\s+get_my_workspace_context\(",
                re.DOTALL,
            ),
            msg="/me/access-context should preserve compatibility via workspace-context payload behavior.",
        )

    def test_entitlement_contract_files_and_package_identity_language(self) -> None:
        self._assert_exists(
            {
                "backend/app/services/entitlement_service.py",
                "backend/app/services/project_entitlement_service.py",
                "backend/app/routes/project_entitlements.py",
                "backend/app/core/package_catalog.py",
                "backend/app/core/package_mapping.py",
                "backend/app/core/package_type_catalog.py",
            },
            "entitlement/package",
        )

        entitlement_route = self._read("backend/app/routes/project_entitlements.py")
        self.assertIn("package_code", entitlement_route)

        package_mapping = self._read("backend/app/core/package_mapping.py")
        for token in ("package_code", "package_slug", "lane", "package_lane"):
            self.assertIn(token, package_mapping)

        contracts_doc = self._read(
            "backend/docs/contracts/continuity_kernel_phase3_contracts.md"
        ).lower()
        self.assertIn("package_code", contracts_doc)
        self.assertIn("package_slug", contracts_doc)
        self.assertRegex(contracts_doc, r"package\s+lane")

    def test_manifest_contract_separation(self) -> None:
        viewer_service = self._file("backend/app/services/viewer_manifest_service.py")
        public_service = self._file("backend/app/services/public_manifest_service.py")

        self.assertTrue(viewer_service.is_file(), "viewer_manifest_service.py must exist")
        self.assertTrue(public_service.is_file(), "public_manifest_service.py must exist")
        self.assertNotEqual(viewer_service.resolve(), public_service.resolve())
        self.assertTrue(self._file("backend/app/routes/viewer_manifest.py").is_file())

        contracts_doc = self._read(
            "backend/docs/contracts/continuity_kernel_phase3_contracts.md"
        ).lower()
        self.assertIn("private runtime viewer payload", contracts_doc)
        self.assertIn("public mint metadata manifest", contracts_doc)

    def test_certificate_contract_boundaries(self) -> None:
        self._assert_exists(
            {
                "backend/app/services/issued_certificate_service.py",
                "backend/app/routes/issued_certificates.py",
                "backend/app/services/lineage_certificate_service.py",
                "backend/app/routes/lineage_certificate.py",
            },
            "certificate",
        )

        issued_service = self._read("backend/app/services/issued_certificate_service.py").lower()
        lineage_service = self._read("backend/app/services/lineage_certificate_service.py").lower()

        self.assertIn("immutable", issued_service)
        self.assertIn("version", issued_service)
        self.assertIn("build_certificate", lineage_service)

        contracts_doc = self._read(
            "backend/docs/contracts/continuity_kernel_phase3_contracts.md"
        ).lower()
        self.assertIn("generated lineage certificate payload", contracts_doc)
        self.assertIn("immutable issued certificate record", contracts_doc)

    def test_mint_readiness_gate_contracts(self) -> None:
        self._assert_exists(
            {
                "backend/app/services/mint_policy_service.py",
                "backend/app/services/mint_record_service.py",
                "backend/app/services/mint_job_service.py",
                "backend/app/routes/mint_policy.py",
                "backend/app/routes/mint_records.py",
            },
            "mint readiness",
        )

        mint_records_route = self._read("backend/app/routes/mint_records.py").lower()
        self.assertIn("eligible", mint_records_route)
        self.assertIn("not ready to queue for minting", mint_records_route)
        self.assertRegex(mint_records_route, r"approve-(admin|customer)")

        contracts_doc = self._read(
            "backend/docs/contracts/continuity_kernel_phase3_contracts.md"
        ).lower()
        for token in ("readiness", "eligibility", "approval", "before queueing mint work"):
            self.assertIn(token, contracts_doc)

    def test_audit_contract_fields_and_privileged_traceability_language(self) -> None:
        self._assert_exists(
            {
                "backend/app/services/audit_log_service.py",
                "backend/app/routes/audit_logs.py",
            },
            "audit",
        )

        audit_service = self._read("backend/app/services/audit_log_service.py")
        for token in ("actor_user_id", "action", "target_type", "target_id", "context"):
            self.assertIn(token, audit_service)

        admin_control_service = self._read("backend/app/services/admin_control_service.py")
        self.assertIn("write_audit_log", admin_control_service)

        contracts_doc = self._read(
            "backend/docs/contracts/continuity_kernel_phase3_contracts.md"
        ).lower()
        self.assertRegex(contracts_doc, r"actor/action/target/context")
        self.assertIn("privileged repair and admin actions remain tied to audit logging", contracts_doc)

    def test_admin_repair_contract_safety_language(self) -> None:
        self._assert_exists(
            {
                "backend/app/services/admin_control_service.py",
                "backend/app/routes/admin_control_center.py",
                "backend/app/routes/admin_maintenance.py",
                "backend/app/services/package_provisioning_service.py",
            },
            "admin repair",
        )

        admin_control_center_route = self._read("backend/app/routes/admin_control_center.py").lower()
        self.assertIn("package-change/apply", admin_control_center_route)
        self.assertIn("reason is required", admin_control_center_route)

        contracts_doc = self._read(
            "backend/docs/contracts/continuity_kernel_phase3_contracts.md"
        ).lower()
        self.assertIn("dry-run/apply", contracts_doc)
        self.assertIn("officer-policy-gated", contracts_doc)


if __name__ == "__main__":
    unittest.main()
