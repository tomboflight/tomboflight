from __future__ import annotations

import json
from typing import Any

from app.config import settings

TRANSFER_EVENT_SIGNATURE = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _lazy_web3():
    try:
        from eth_account import Account
        from web3 import Web3
    except ImportError as exc:
        raise RuntimeError(
            "web3 and eth-account are required for live blockchain minting. "
            "Install backend requirements before enabling NFT mint jobs."
        ) from exc

    return Web3, Account


def _require_mint_runtime() -> None:
    if not settings.nft_mint_enabled:
        raise RuntimeError("NFT minting is disabled by configuration.")

    missing = [
        name
        for name, value in (
            ("NFT_CONTRACT_ADDRESS", settings.nft_contract_address),
            ("NFT_CONTRACT_ABI_JSON", settings.nft_contract_abi_json),
            ("NFT_MINTER_PRIVATE_KEY", settings.nft_minter_private_key),
            ("NFT_RPC_URL", settings.nft_rpc_url),
        )
        if not _normalize(value)
    ]
    if missing:
        missing_joined = ", ".join(missing)
        raise RuntimeError(
            f"NFT minting is not fully configured. Missing: {missing_joined}."
        )


def _web3_client():
    Web3, _Account = _lazy_web3()
    client = Web3(Web3.HTTPProvider(_normalize(settings.nft_rpc_url)))
    if not client.is_connected():
        raise RuntimeError("Unable to connect to the configured NFT RPC endpoint.")
    return client


def _contract_abi() -> list[dict[str, Any]]:
    raw = _normalize(settings.nft_contract_abi_json)
    if not raw:
        raise RuntimeError("NFT contract ABI is not configured.")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("NFT contract ABI JSON is invalid.") from exc
    if not isinstance(parsed, list):
        raise RuntimeError("NFT contract ABI must be a JSON array.")
    return parsed


def _account():
    _Web3, Account = _lazy_web3()
    return Account.from_key(_normalize(settings.nft_minter_private_key))


def _checksum_address(address: str) -> str:
    Web3, _Account = _lazy_web3()
    return Web3.to_checksum_address(_normalize(address))


def _recipient_wallet(recipient_wallet: str | None) -> str:
    preferred = _normalize(recipient_wallet) or _normalize(settings.nft_default_recipient_wallet)
    if preferred:
        return _checksum_address(preferred)
    raise RuntimeError(
        "A recipient wallet is required before minting. "
        "Provide a customer wallet or configure NFT_DEFAULT_RECIPIENT_WALLET."
    )


def _token_type_argument(token_type: str, input_type: str) -> Any:
    normalized_token_type = _normalize(token_type)
    normalized_input_type = _normalize(input_type).lower()

    if normalized_input_type.startswith("string"):
        return normalized_token_type

    if normalized_input_type.startswith("uint") or normalized_input_type.startswith("int"):
        token_map = {
            "portrait_anchor": 1,
            "household_anchor": 2,
            "branch_anchor": 3,
            "organization_anchor": 4,
        }
        if normalized_token_type.isdigit():
            return int(normalized_token_type)
        if normalized_token_type in token_map:
            return token_map[normalized_token_type]
        raise RuntimeError(
            f"Token type '{normalized_token_type}' cannot be converted to numeric contract input."
        )

    if normalized_input_type == "bytes32":
        raw = normalized_token_type.encode("utf-8")
        if len(raw) > 32:
            raise RuntimeError("Token type is too long for bytes32 contract input.")
        return raw.ljust(32, b"\x00")

    raise RuntimeError(
        f"Unsupported token type input '{normalized_input_type}' in mint contract."
    )


def _contract_function(contract: Any, *, recipient: str, metadata_uri: str, token_type: str):
    function_name = _normalize(settings.nft_mint_function_name) or "mintAnchor"
    candidate = getattr(contract.functions, function_name, None)
    if candidate is None:
        raise RuntimeError(f"Mint function '{function_name}' was not found in the contract ABI.")

    functions_abi = [
        item
        for item in _contract_abi()
        if item.get("type") == "function" and item.get("name") == function_name
    ]
    if not functions_abi:
        raise RuntimeError(f"Mint function '{function_name}' was not found in the ABI.")

    abi = functions_abi[0]
    arguments: list[Any] = []
    string_index = 0
    token_type_consumed = False

    for input_item in abi.get("inputs", []):
        input_type = _normalize(input_item.get("type")).lower()
        if input_type == "address":
            arguments.append(recipient)
            continue
        if input_type.startswith("string"):
            if string_index == 0:
                arguments.append(metadata_uri)
            else:
                arguments.append(_token_type_argument(token_type, input_type))
                token_type_consumed = True
            string_index += 1
            continue
        if input_type.startswith("uint") or input_type.startswith("int") or input_type == "bytes32":
            arguments.append(_token_type_argument(token_type, input_type))
            token_type_consumed = True
            continue
        raise RuntimeError(
            f"Unsupported mint function input type '{input_type}'. "
            "Expected address, string, uint, int, or bytes32 parameters only."
        )

    if not token_type_consumed:
        raise RuntimeError(
            "Mint function ABI does not expose a token type argument. "
            "Update NFT_MINT_FUNCTION_NAME or contract ABI configuration."
        )

    return candidate(*arguments)


def _gas_fields(client: Any) -> dict[str, int]:
    gas_price = int(client.eth.gas_price)
    try:
        priority_fee = int(client.eth.max_priority_fee)
    except Exception:
        priority_fee = max(gas_price // 10, 1)

    return {
        "maxPriorityFeePerGas": priority_fee,
        "maxFeePerGas": max(gas_price + priority_fee, gas_price),
    }


def _extract_token_id_from_receipt(receipt: Any) -> str | None:
    logs = getattr(receipt, "logs", None) or receipt.get("logs") or []
    for log in logs:
        topics = list(getattr(log, "topics", None) or log.get("topics") or [])
        if len(topics) < 4:
            continue
        first_topic = topics[0]
        topic_hex = first_topic.hex() if hasattr(first_topic, "hex") else str(first_topic)
        if not topic_hex.lower().startswith(TRANSFER_EVENT_SIGNATURE):
            continue
        token_topic = topics[3]
        token_hex = token_topic.hex() if hasattr(token_topic, "hex") else str(token_topic)
        try:
            return str(int(token_hex, 16))
        except Exception:
            continue
    return None


def mint_anchor(
    *,
    metadata_uri: str,
    recipient_wallet: str | None,
    token_type: str,
) -> dict[str, Any]:
    _require_mint_runtime()

    client = _web3_client()
    contract = client.eth.contract(
        address=_checksum_address(settings.nft_contract_address),
        abi=_contract_abi(),
    )
    signer = _account()
    recipient = _recipient_wallet(recipient_wallet)
    contract_function = _contract_function(
        contract,
        recipient=recipient,
        metadata_uri=metadata_uri,
        token_type=token_type,
    )

    transaction = contract_function.build_transaction(
        {
            "from": signer.address,
            "nonce": client.eth.get_transaction_count(signer.address),
            "chainId": int(client.eth.chain_id),
            **_gas_fields(client),
        }
    )

    if not transaction.get("gas"):
        estimated_gas = contract_function.estimate_gas({"from": signer.address})
        transaction["gas"] = int(estimated_gas * 1.2)

    signed = client.eth.account.sign_transaction(
        transaction,
        private_key=_normalize(settings.nft_minter_private_key),
    )
    tx_hash = client.eth.send_raw_transaction(signed.raw_transaction)
    tx_hash_hex = tx_hash.hex()

    receipt = None
    try:
        receipt = client.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    except Exception as exc:
        if exc.__class__.__name__ not in {"TimeExhausted", "TimeoutError"}:
            raise

    if receipt is not None and int(receipt.status) != 1:
        raise RuntimeError("Mint transaction was mined but reverted on-chain.")

    token_id = _extract_token_id_from_receipt(receipt) if receipt is not None else None

    return {
        "status": "submitted",
        "chain": _normalize(settings.nft_chain),
        "contract_address": _checksum_address(settings.nft_contract_address),
        "tx_hash": tx_hash_hex,
        "token_id": token_id,
        "recipient_wallet": recipient,
        "block_number": int(receipt.blockNumber) if receipt is not None else None,
    }


def sync_mint_receipt(tx_hash: str) -> dict[str, Any]:
    _require_mint_runtime()

    client = _web3_client()
    try:
        receipt = client.eth.get_transaction_receipt(_normalize(tx_hash))
    except Exception as exc:
        if exc.__class__.__name__ == "TransactionNotFound":
            return {
                "status": "pending",
                "chain": _normalize(settings.nft_chain),
                "contract_address": _checksum_address(settings.nft_contract_address),
                "tx_hash": _normalize(tx_hash),
                "token_id": None,
                "block_number": None,
            }
        raise
    token_id = _extract_token_id_from_receipt(receipt)

    return {
        "status": "confirmed" if int(receipt.status) == 1 else "failed",
        "chain": _normalize(settings.nft_chain),
        "contract_address": _checksum_address(settings.nft_contract_address),
        "tx_hash": _normalize(tx_hash),
        "token_id": token_id,
        "block_number": int(receipt.blockNumber),
    }
