import unittest

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


if __name__ == "__main__":
    unittest.main()
