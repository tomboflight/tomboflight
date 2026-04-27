import sys
import unittest
from unittest.mock import patch

from scripts import enforce_account_separation


class AccountSeparationScriptContractTests(unittest.TestCase):
    def test_larry_personal_account_is_targeted_for_package_experience(self):
        config = enforce_account_separation.TARGET_PERSONAL_ACCOUNT_EXPERIENCE.get(
            "larrycr27@gmail.com"
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


if __name__ == "__main__":
    unittest.main()
