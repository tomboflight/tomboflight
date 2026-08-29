import asyncio
import unittest
from unittest.mock import patch

from app import main as main_module


class StartupInitializationTests(unittest.TestCase):
    def test_lifespan_fails_before_connecting_when_runtime_environment_is_unsafe(self):
        async def _run():
            async with main_module.lifespan(main_module.app):
                return None

        with (
            patch.object(
                main_module,
                "validate_runtime_environment_on_startup",
                side_effect=RuntimeError("unsafe hosted environment"),
            ),
            patch.object(
                main_module,
                "validate_admin_identity_registry_configuration",
            ) as identity_validate_mock,
            patch.object(main_module, "connect_to_mongo") as connect_mock,
        ):
            with self.assertRaisesRegex(RuntimeError, "unsafe hosted environment"):
                asyncio.run(_run())

        identity_validate_mock.assert_not_called()
        connect_mock.assert_not_called()

    def test_lifespan_runs_index_initializers(self):
        async def _run():
            async with main_module.lifespan(main_module.app):
                return None

        with (
            patch.object(main_module, "validate_runtime_environment_on_startup") as environment_validate_mock,
            patch.object(main_module, "validate_admin_identity_registry_configuration") as identity_validate_mock,
            patch.object(main_module, "validate_nft_runtime_configuration_on_startup") as validate_mock,
            patch.object(main_module, "connect_to_mongo", return_value={"db": "ok"}) as connect_mock,
            patch.object(main_module, "ensure_auth_indexes") as auth_index_mock,
            patch.object(main_module, "ensure_rate_limit_indexes") as rate_limit_index_mock,
            patch.object(main_module, "initialize_order_indexes") as order_init_mock,
            patch.object(main_module, "ensure_project_entitlement_indexes") as entitlement_init_mock,
            patch.object(main_module, "initialize_mint_record_indexes") as mint_record_init_mock,
            patch.object(main_module, "initialize_mint_job_indexes") as mint_job_init_mock,
            patch.object(main_module, "ensure_stripe_event_indexes") as stripe_init_mock,
            patch.object(main_module, "ensure_finance_event_indexes") as finance_init_mock,
            patch.object(main_module, "ensure_bridge_event_invite_indexes") as bridge_event_init_mock,
            patch.object(main_module, "ensure_continuity_runtime_indexes") as continuity_init_mock,
            patch.object(main_module, "ensure_organization_indexes") as organization_init_mock,
            patch.object(main_module, "ensure_cinematic_manifest_indexes") as cinematic_init_mock,
            patch.object(main_module, "ensure_runtime_data_indexes") as runtime_data_index_mock,
            patch.object(main_module, "bootstrap_admin_access_controls") as admin_access_bootstrap_mock,
            patch.object(main_module, "close_mongo_connection") as close_mock,
        ):
            asyncio.run(_run())

        environment_validate_mock.assert_called_once()
        identity_validate_mock.assert_called_once()
        validate_mock.assert_called_once()
        connect_mock.assert_called_once()
        auth_index_mock.assert_called_once()
        rate_limit_index_mock.assert_called_once()
        order_init_mock.assert_called_once()
        entitlement_init_mock.assert_called_once()
        mint_record_init_mock.assert_called_once()
        mint_job_init_mock.assert_called_once()
        stripe_init_mock.assert_called_once()
        finance_init_mock.assert_called_once()
        bridge_event_init_mock.assert_called_once()
        continuity_init_mock.assert_called_once()
        organization_init_mock.assert_called_once()
        cinematic_init_mock.assert_called_once()
        runtime_data_index_mock.assert_called_once()
        admin_access_bootstrap_mock.assert_called_once()
        close_mock.assert_called_once()

    def test_lifespan_degraded_mode_when_mongo_unavailable(self):
        async def _run():
            async with main_module.lifespan(main_module.app):
                return None

        with (
            patch.object(main_module, "validate_runtime_environment_on_startup") as environment_validate_mock,
            patch.object(main_module, "validate_admin_identity_registry_configuration") as identity_validate_mock,
            patch.object(main_module, "validate_nft_runtime_configuration_on_startup") as validate_mock,
            patch.object(main_module, "connect_to_mongo", return_value=None) as connect_mock,
            patch.object(main_module, "ensure_auth_indexes") as auth_index_mock,
            patch.object(main_module, "ensure_rate_limit_indexes") as rate_limit_index_mock,
            patch.object(main_module, "initialize_order_indexes") as order_init_mock,
            patch.object(main_module, "ensure_project_entitlement_indexes") as entitlement_init_mock,
            patch.object(main_module, "initialize_mint_record_indexes") as mint_record_init_mock,
            patch.object(main_module, "initialize_mint_job_indexes") as mint_job_init_mock,
            patch.object(main_module, "ensure_stripe_event_indexes") as stripe_init_mock,
            patch.object(main_module, "ensure_finance_event_indexes") as finance_init_mock,
            patch.object(main_module, "ensure_bridge_event_invite_indexes") as bridge_event_init_mock,
            patch.object(main_module, "ensure_continuity_runtime_indexes") as continuity_init_mock,
            patch.object(main_module, "ensure_organization_indexes") as organization_init_mock,
            patch.object(main_module, "ensure_cinematic_manifest_indexes") as cinematic_init_mock,
            patch.object(main_module, "ensure_runtime_data_indexes") as runtime_data_index_mock,
            patch.object(main_module, "bootstrap_admin_access_controls") as admin_access_bootstrap_mock,
            patch.object(main_module, "close_mongo_connection") as close_mock,
        ):
            asyncio.run(_run())

        environment_validate_mock.assert_called_once()
        identity_validate_mock.assert_called_once()
        validate_mock.assert_called_once()
        connect_mock.assert_called_once()
        auth_index_mock.assert_not_called()
        rate_limit_index_mock.assert_not_called()
        order_init_mock.assert_not_called()
        entitlement_init_mock.assert_not_called()
        mint_record_init_mock.assert_not_called()
        mint_job_init_mock.assert_not_called()
        stripe_init_mock.assert_not_called()
        finance_init_mock.assert_not_called()
        bridge_event_init_mock.assert_not_called()
        continuity_init_mock.assert_not_called()
        organization_init_mock.assert_not_called()
        cinematic_init_mock.assert_not_called()
        runtime_data_index_mock.assert_not_called()
        admin_access_bootstrap_mock.assert_not_called()
        close_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
