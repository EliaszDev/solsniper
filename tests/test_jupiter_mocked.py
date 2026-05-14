#!/usr/bin/env python3
"""Mocked unit tests for Steps 1-5 — no external network required."""
import asyncio
import base64
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ["HELIUS_API_KEY"] = "test_key"
os.environ["SECRET_KEY"] = "test_secret"
os.environ["PAPER_TRADING"] = "true"

import base58
from solders.keypair import Keypair
from solders.transaction import Transaction

from backend.services.jupiter import JupiterClient, _SOL_MINT

TEST_KP = Keypair()
TEST_PUBKEY = str(TEST_KP.pubkey())
TEST_PRIVKEY = base58.b58encode(bytes(TEST_KP.to_bytes_array())).decode("ascii")
os.environ["WALLET_PRIVATE_KEY"] = TEST_PRIVKEY

FAKE_SOL_PRICE = 150.0
FAKE_QUOTE = {
    "inputMint": _SOL_MINT,
    "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "inAmount": "66666666",
    "outAmount": "1234567890",
    "otherAmountThreshold": "1234000000",
    "swapMode": "ExactIn",
    "slippageBps": 100,
    "routePlan": [],
}
def _make_fake_tx(kp: Keypair) -> str:
    """Generate a valid base64-encoded legacy tx for signing tests."""
    from solders.message import Message
    from solders.transaction import Transaction
    from solders.pubkey import Pubkey
    from solders.hash import Hash
    from solders.instruction import Instruction

    program = Pubkey.new_unique()
    ix = Instruction(program, b'', [])
    msg = Message.new_with_blockhash([ix], kp.pubkey(), Hash.new_unique())
    tx = Transaction.new_unsigned(msg)
    tx.sign([kp], msg.recent_blockhash)
    return base64.b64encode(bytes(tx)).decode("ascii")


FAKE_SWAP_TX_BASE64 = _make_fake_tx(TEST_KP)


def _make_response(data, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


async def test_step1_get_quote():
    print("=" * 60)
    print("STEP 1: get_quote (mocked)")
    print("=" * 60)

    client = JupiterClient()
    mock_http = AsyncMock()
    mock_http.is_closed = False

    # Mock DexScreener SOL price response
    dex_resp = _make_response({
        "pairs": [
            {"priceUsd": str(FAKE_SOL_PRICE), "liquidity": {"usd": "1000000"}}
        ]
    })
    # Mock Jupiter quote response
    jup_resp = _make_response(FAKE_QUOTE)
    mock_http.get.side_effect = [dex_resp, jup_resp]
    client._client = mock_http

    quote = await client.get_quote("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", 10.0)

    assert quote["outAmount"] == "1234567890"
    print(f"  outAmount: {quote['outAmount']}")
    print("  ✓ PASS\n")
    return quote


async def test_step2_build_swap_tx(quote):
    print("=" * 60)
    print("STEP 2: build_swap_tx (mocked)")
    print("=" * 60)

    client = JupiterClient()
    mock_http = AsyncMock()
    mock_http.is_closed = False
    mock_http.post.return_value = _make_response({"swapTransaction": FAKE_SWAP_TX_BASE64})
    client._client = mock_http

    tx_b64 = await client.build_swap_tx(quote, TEST_PUBKEY)

    assert tx_b64 == FAKE_SWAP_TX_BASE64
    print(f"  base64 len: {len(tx_b64)}")
    print("  ✓ PASS\n")
    return tx_b64


async def test_step3_sign_tx(tx_b64):
    print("=" * 60)
    print("STEP 3: sign_tx")
    print("=" * 60)

    client = JupiterClient()
    signed = client.sign_tx(tx_b64)

    assert len(signed) > 0
    print(f"  signed bytes: {len(signed)}")

    # Verify it's a valid Transaction by deserializing
    tx = Transaction.from_bytes(signed)
    assert len(tx.signatures) >= 1
    print(f"  signatures count: {len(tx.signatures)}")
    print("  ✓ PASS\n")
    return signed


async def test_step4_submit_confirm(signed):
    print("=" * 60)
    print("STEP 4: submit_tx + confirm_tx (paper mode)")
    print("=" * 60)

    client = JupiterClient()
    sig = await client.submit_tx(signed)

    assert sig.startswith("PAPER_")
    print(f"  signature: {sig}")

    confirmed = await client.confirm_tx(sig)
    assert confirmed is True
    print(f"  confirmed: {confirmed}")
    print("  ✓ PASS\n")


async def test_step5_execute_swap():
    print("=" * 60)
    print("STEP 5: execute_swap (fully mocked)")
    print("=" * 60)

    client = JupiterClient()
    mock_http = AsyncMock()
    mock_http.is_closed = False
    mock_http.get.side_effect = [
        _make_response({"pairs": [{"priceUsd": "150.0", "liquidity": {"usd": "1000000"}}]}),  # DexScreener
        _make_response(FAKE_QUOTE),  # Jupiter /quote
    ]
    mock_http.post.side_effect = [
        _make_response({"swapTransaction": FAKE_SWAP_TX_BASE64}),  # Jupiter /swap
    ]
    client._client = mock_http

    result = await client.execute_swap("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", 10.0, TEST_PUBKEY)

    assert result["success"] is True
    assert result["signature"].startswith("PAPER_")
    assert result["out_amount"] == "1234567890"
    print(f"  success: {result['success']}")
    print(f"  signature: {result['signature']}")
    print(f"  out_amount: {result['out_amount']}")
    print(f"  error: {result['error']}")
    print("  ✓ PASS\n")


async def main():
    print(f"Test wallet pubkey: {TEST_PUBKEY}\n")

    quote = await test_step1_get_quote()
    tx_b64 = await test_step2_build_swap_tx(quote)
    signed = await test_step3_sign_tx(tx_b64)
    await test_step4_submit_confirm(signed)
    await test_step5_execute_swap()

    print("=" * 60)
    print("ALL 5 STEPS PASSED ✓")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
