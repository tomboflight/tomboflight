import os
import tempfile
import unittest
from typing import Any, cast
from unittest.mock import patch

from app.config import Settings


class ConfigEmailAliasTests(unittest.TestCase):
    def _settings_from_env(self) -> Settings:
        # Pydantic Settings accepts `_env_file` at runtime; cast to satisfy static typing.
        settings_type = cast(Any, Settings)
        return settings_type(_env_file=None)

    def test_postmark_token_aliases_are_accepted(self):
        with patch.dict(
            os.environ,
            {
                "POSTMARK_TOKEN": "alias-token-value",
            },
            clear=True,
        ):
            settings = self._settings_from_env()
        self.assertEqual(settings.postmark_server_token, "alias-token-value")

    def test_postmark_extended_aliases_are_accepted(self):
        with patch.dict(
            os.environ,
            {
                "POSTMARK_SERVER_API_TOKEN": "extended-alias-token",
            },
            clear=True,
        ):
            settings = self._settings_from_env()
        self.assertEqual(settings.postmark_server_token, "extended-alias-token")

    def test_postmark_token_file_alias_is_loaded(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write("file-token-value\n")
            token_file = handle.name
        try:
            with patch.dict(
                os.environ,
                {
                    "POSTMARK_SERVER_TOKEN_FILE": token_file,
                },
                clear=True,
            ):
                settings = self._settings_from_env()
            self.assertEqual(settings.postmark_server_token_file, token_file)
        finally:
            os.unlink(token_file)


if __name__ == "__main__":
    unittest.main()
