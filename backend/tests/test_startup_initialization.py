import asyncio
import unittest
from unittest.mock import patch

from app import main as main_module


class StartupInitializationTests(unittest.TestCase):
    def test_lifespan_runs_index_initializers(self):
        async def _run():
            async with main_module.lifespan(main_module.app):
                return None

        with (
            patch.object(main_module, "validate_nft_runtime_configuration_on_startup") as validate_mock,
            patch.object(main_module, "connect_to_mongo") as connect_mock,
            patch.object(main_module, "get_database", return_value={"db": "ok"}) as get_db_mock,
            patch.object(main_module, "initialize_order_indexes") as order_init_mock,
            patch.object(main_module, "initialize_mint_record_indexes") as mint_record_init_mock,
            patch.object(main_module, "initialize_mint_job_indexes") as mint_job_init_mock,
            patch.object(main_module, "ensure_stripe_event_indexes") as stripe_init_mock,
            patch.object(main_module, "close_mongo_connection") as close_mock,
        ):
            asyncio.run(_run())

        validate_mock.assert_called_once()
        connect_mock.assert_called_once()
        get_db_mock.assert_called_once()
        order_init_mock.assert_called_once()
        mint_record_init_mock.assert_called_once()
        mint_job_init_mock.assert_called_once()
        stripe_init_mock.assert_called_once()
        close_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
