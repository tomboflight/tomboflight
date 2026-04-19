import os
import unittest
from unittest.mock import patch

from app.config import Settings


class ConfigEmailAliasTests(unittest.TestCase):
    def test_postmark_token_aliases_are_accepted(self):
        with patch.dict(
            os.environ,
            {
                "POSTMARK_TOKEN": "alias-token-value",
            },
            clear=True,
        ):
            settings = Settings(_env_file=None)
        self.assertEqual(settings.postmark_server_token, "alias-token-value")


if __name__ == "__main__":
    unittest.main()
