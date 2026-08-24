from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import blockchain_mint_service, nft_runtime_validation_service


CONTRACT_ADDRESS = "0x39967cEb7580aB9110b349Ca3a7fe0179b950Ba5"
OWNER_ADDRESS = "0x8d378Fd7f03fF30787827E2bB0C9486776531db9"
OTHER_ADDRESS = "0x65ec400000000000000000000000000000049204"


class _OwnerCall:
    def __init__(self, owner_address: str):
        self.owner_address = owner_address

    def __call__(self):
        return self

    def call(self):
        return self.owner_address


class _Contract:
    def __init__(self, owner_address: str | None):
        self.functions = SimpleNamespace()
        if owner_address is not None:
            self.functions.owner = _OwnerCall(owner_address)


class _ForbiddenSigningAccount:
    def sign_transaction(self, *_args, **_kwargs):
        raise AssertionError("startup preflight must never sign a transaction")


class _Eth:
    def __init__(self, *, chain_id: int, owner_address: str | None):
        self.chain_id = chain_id
        self.account = _ForbiddenSigningAccount()
        self._owner_address = owner_address
        self.contract_calls: list[dict] = []

    def contract(self, **kwargs):
        self.contract_calls.append(kwargs)
        return _Contract(self._owner_address)

    def send_raw_transaction(self, *_args, **_kwargs):
        raise AssertionError("startup preflight must never broadcast a transaction")


class _Client:
    def __init__(self, *, chain_id: int = 8453, owner_address: str | None = OWNER_ADDRESS):
        self.eth = _Eth(chain_id=chain_id, owner_address=owner_address)


class NftSignerOwnerPreflightTests(unittest.TestCase):
    def _runtime_settings(self):
        return patch.multiple(
            blockchain_mint_service.settings,
            nft_mint_enabled=True,
            nft_chain="base-mainnet",
            nft_rpc_url="https://mainnet.base.org",
            nft_contract_address=CONTRACT_ADDRESS,
            nft_contract_abi_json='[{"type":"function","name":"owner"}]',
            nft_minter_private_key="1" * 64,
        )

    def _preflight_patches(self, client: _Client, *, signer_address: str = OWNER_ADDRESS):
        return (
            patch.object(blockchain_mint_service, "_web3_client", return_value=client),
            patch.object(
                blockchain_mint_service,
                "_checksum_address",
                side_effect=lambda address, **_kwargs: address,
            ),
            patch.object(
                blockchain_mint_service,
                "_account",
                return_value=SimpleNamespace(address=signer_address),
            ),
        )

    def test_matching_signer_and_owner_pass_without_signing_or_broadcasting(self):
        client = _Client()
        web3_patch, checksum_patch, account_patch = self._preflight_patches(client)
        with self._runtime_settings(), web3_patch, checksum_patch, account_patch:
            result = blockchain_mint_service.validate_mint_signer_contract_owner()

        self.assertTrue(result["verified"])
        self.assertEqual(result["chain_id"], 8453)
        self.assertEqual(result["signer_address"], OWNER_ADDRESS)
        self.assertEqual(result["contract_owner"], OWNER_ADDRESS)
        self.assertEqual(len(client.eth.contract_calls), 1)

    def test_mismatched_signer_fails_closed_before_any_transaction_action(self):
        client = _Client()
        web3_patch, checksum_patch, account_patch = self._preflight_patches(
            client,
            signer_address=OTHER_ADDRESS,
        )
        with self._runtime_settings(), web3_patch, checksum_patch, account_patch:
            with self.assertRaisesRegex(
                RuntimeError,
                "not the owner of the NFT contract",
            ):
                blockchain_mint_service.validate_mint_signer_contract_owner()

    def test_wrong_rpc_chain_fails_closed_before_contract_access(self):
        client = _Client(chain_id=1)
        web3_patch, checksum_patch, account_patch = self._preflight_patches(client)
        with self._runtime_settings(), web3_patch, checksum_patch, account_patch:
            with self.assertRaisesRegex(RuntimeError, "wrong chain"):
                blockchain_mint_service.validate_mint_signer_contract_owner()

        self.assertEqual(client.eth.contract_calls, [])

    def test_contract_without_owner_function_fails_closed(self):
        client = _Client(owner_address=None)
        web3_patch, checksum_patch, account_patch = self._preflight_patches(client)
        with self._runtime_settings(), web3_patch, checksum_patch, account_patch:
            with self.assertRaisesRegex(RuntimeError, "does not expose owner"):
                blockchain_mint_service.validate_mint_signer_contract_owner()

    def test_unavailable_rpc_fails_closed(self):
        with (
            self._runtime_settings(),
            patch.object(
                blockchain_mint_service,
                "_web3_client",
                side_effect=RuntimeError("Unable to connect to the configured NFT RPC endpoint."),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "Unable to connect"):
                blockchain_mint_service.validate_mint_signer_contract_owner()

    def test_startup_validation_invokes_live_owner_preflight(self):
        with (
            patch.multiple(
                nft_runtime_validation_service.settings,
                nft_mint_enabled=True,
                nft_mint_worker_enabled=True,
                nft_auto_mint_on_review_enabled=False,
                nft_chain="base-mainnet",
                nft_rpc_url="https://mainnet.base.org",
                nft_contract_address=CONTRACT_ADDRESS,
                nft_contract_abi_json='[{"type":"function","name":"owner"}]',
                nft_minter_private_key="1" * 64,
                hash_salt="2" * 64,
                metadata_base_url="https://metadata.tomboflight.com/v1",
                poster_base_url="https://posters.tomboflight.com/v1",
                public_token_external_base_url="https://tomboflight.com/public",
            ),
            patch.object(nft_runtime_validation_service, "_validate_http_url"),
            patch.object(nft_runtime_validation_service, "_validate_contract_address"),
            patch.object(nft_runtime_validation_service, "_validate_private_key"),
            patch.object(nft_runtime_validation_service, "_validate_contract_abi"),
            patch.object(nft_runtime_validation_service, "_validate_r2_configuration"),
            patch.object(
                nft_runtime_validation_service,
                "validate_mint_signer_contract_owner",
                return_value={"verified": True},
            ) as preflight,
        ):
            nft_runtime_validation_service.validate_nft_runtime_configuration_on_startup()

        preflight.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
