import sys
import unittest
from unittest.mock import patch

from scripts import enforce_account_separation


class AccountSeparationScriptContractTests(unittest.TestCase):
    def test_legacy_personal_account_is_targeted_for_package_experience(self):
        config = enforce_account_separation.TARGET_PERSONAL_ACCOUNT_EXPERIENCE.get(
            "legacy-customer@example.com"
        )
        self.assertIsNotNone(config)
        assert config is not None
        self.assertEqual(config.get("package_code"), "legacy_plus")
        self.assertTrue(bool(str(config.get("project_name") or "").strip()))
        self.assertTrue(bool(str(config.get("wallet_address") or "").strip()))

    def test_apply_flag_is_rejected_and_does_not_connect_to_database(self):
        with (
            patch.object(sys, "argv", ["enforce_account_separation.py", "--apply"]),
            patch.object(enforce_account_separation, "connect_to_mongo") as connect_mock,
        ):
            result = enforce_account_separation.main()
        self.assertEqual(result, 2)
        connect_mock.assert_not_called()

    def test_dry_run_requires_private_audit_targets_before_database_access(self):
        with (
            patch.object(sys, "argv", ["enforce_account_separation.py"]),
            patch.object(
                enforce_account_separation,
                "validate_admin_identity_registry_configuration",
            ),
            patch.object(
                enforce_account_separation,
                "_validate_account_separation_audit_targets",
                side_effect=RuntimeError("private audit targets missing"),
            ),
            patch.object(enforce_account_separation, "connect_to_mongo") as connect_mock,
        ):
            with self.assertRaisesRegex(RuntimeError, "private audit targets missing"):
                enforce_account_separation.main()

        connect_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
