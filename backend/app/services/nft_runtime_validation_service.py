from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from app.config import settings
from app.services.r2_storage_service import r2_is_configured

EVM_WALLET_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")
HEX_PRIVATE_KEY_PATTERN = re.compile(r"^(0x)?[a-fA-F0-9]{64}$")


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _is_local_environment() -> bool:
    return _normalize(settings.environment).lower() in {
        "",
        "development",
        "dev",
        "local",
        "test",
        "testing",
    }


def _validate_http_url(value: str, *, field_name: str, require_v1_path: bool = False) -> None:
    parsed = urlparse(_normalize(value))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError(f"{field_name} must be a valid http(s) URL.")
    if require_v1_path and not parsed.path.rstrip("/").endswith("/v1"):
        raise RuntimeError(f"{field_name} must end with /v1.")


def _validate_contract_address() -> None:
    if not EVM_WALLET_PATTERN.fullmatch(_normalize(settings.nft_contract_address)):
        raise RuntimeError("NFT_CONTRACT_ADDRESS must be a valid EVM contract address.")


def _validate_private_key() -> None:
    private_key = _normalize(settings.nft_minter_private_key)
    if not HEX_PRIVATE_KEY_PATTERN.fullmatch(private_key):
        raise RuntimeError("NFT_MINTER_PRIVATE_KEY must be a 32-byte hex private key.")
    if EVM_WALLET_PATTERN.fullmatch(private_key):
        raise RuntimeError("NFT_MINTER_PRIVATE_KEY appears to be a wallet address, not a private key.")


def _validate_contract_abi() -> None:
    raw = _normalize(settings.nft_contract_abi_json)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("NFT_CONTRACT_ABI_JSON is not valid JSON.") from exc
    if not isinstance(parsed, list):
        raise RuntimeError("NFT_CONTRACT_ABI_JSON must be a JSON array.")


def _validate_r2_configuration() -> None:
    missing_buckets: list[str] = []
    if not _normalize(settings.r2_metadata_bucket) and not _normalize(settings.r2_bucket):
        missing_buckets.append("R2_METADATA_BUCKET")
    if not _normalize(settings.r2_poster_bucket) and not _normalize(settings.r2_bucket):
        missing_buckets.append("R2_POSTER_BUCKET")

    if missing_buckets:
        raise RuntimeError(
            "R2 public buckets are not fully configured. Missing: "
            + ", ".join(missing_buckets)
        )

    if not r2_is_configured() and not _is_local_environment():
        raise RuntimeError(
            "R2 storage is not fully configured for this environment. "
            "Set the R2 endpoint, credentials, and public buckets before enabling NFT minting."
        )


def validate_nft_runtime_configuration_on_startup() -> None:
    if not settings.nft_mint_enabled:
        return

    missing: list[str] = []
    for field_name, value in (
        ("NFT_CHAIN", settings.nft_chain),
        ("NFT_RPC_URL", settings.nft_rpc_url),
        ("NFT_CONTRACT_ADDRESS", settings.nft_contract_address),
        ("NFT_CONTRACT_ABI_JSON", settings.nft_contract_abi_json),
        ("NFT_MINTER_PRIVATE_KEY", settings.nft_minter_private_key),
        ("HASH_SALT", settings.hash_salt),
        ("METADATA_BASE_URL", settings.metadata_base_url),
        ("POSTER_BASE_URL", settings.poster_base_url),
        ("PUBLIC_TOKEN_EXTERNAL_BASE_URL", settings.public_token_external_base_url),
    ):
        if not _normalize(value):
            missing.append(field_name)

    if missing:
        raise RuntimeError(
            "NFT minting startup validation failed. Missing required settings: "
            + ", ".join(missing)
        )

    _validate_http_url(settings.nft_rpc_url, field_name="NFT_RPC_URL")
    _validate_http_url(
        settings.metadata_base_url_clean,
        field_name="METADATA_BASE_URL",
        require_v1_path=True,
    )
    _validate_http_url(
        settings.poster_base_url_clean,
        field_name="POSTER_BASE_URL",
        require_v1_path=True,
    )
    _validate_http_url(
        settings.public_token_external_base_url_clean,
        field_name="PUBLIC_TOKEN_EXTERNAL_BASE_URL",
    )
    _validate_contract_address()
    _validate_private_key()
    _validate_contract_abi()
    _validate_r2_configuration()
