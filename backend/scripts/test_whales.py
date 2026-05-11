"""
Week 1 Test Script: Query 3 known whale wallets via Helius API.

Usage:
    cd /home/vboxuser/nanobot/workspace/solsniper
    python -m backend.scripts.test_whales

Requires HELIUS_API_KEY in .env
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

# add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from backend.services.helius import HeliusClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)

# 3 well-known high-activity Solana wallets (public)
TEST_WALLETS = [
    {
        "address": "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVbNUqDG9JzjeE",
        "label": "Jupiter Aggregator V4",
    },
    {
        "address": "H8sMJSCQxfKiFTLWy45j9sK6ML6dXB2G4dq2wHVySvg1",
        "label": "Raydium AMM V4",
    },
    {
        "address": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
        "label": "Pump.fun bonding curve",
    },
]


async def main():
    logger.info("=" * 60)
    logger.info("Week 1 Test: Helius Wallet History Polling")
    logger.info("=" * 60)

    try:
        async with HeliusClient() as client:
            for w in TEST_WALLETS:
                addr = w["address"]
                label = w["label"]
                logger.info("\n--- Querying %s (%s) ---", label, addr[:12] + "...")

                swaps = await client.get_wallet_swaps(addr, limit=5)
                logger.info("Found %d SWAP transaction(s)", len(swaps))

                for i, s in enumerate(swaps[:3], 1):
                    logger.info(
                        "  [%d] %s | %s | in=%s (%.4f) → out=%s (%.4f) | SOLΔ=%.6f",
                        i,
                        s.direction.upper(),
                        s.signature[:20] + "...",
                        s.token_mint_in[:12] + "..." if len(s.token_mint_in) > 12 else s.token_mint_in,
                        s.amount_in,
                        s.token_mint_out[:12] + "..." if len(s.token_mint_out) > 12 else s.token_mint_out,
                        s.amount_out,
                        s.sol_delta,
                    )

                # also dump raw first tx for inspection
                raw = await client.get_wallet_history(addr, limit=1)
                if raw:
                    out_file = Path(f"/tmp/helius_{addr[:8]}.json")
                    out_file.write_text(json.dumps(raw[0], indent=2))
                    logger.info("  Raw tx saved to %s", out_file)

            # test multi-wallet poll
            logger.info("\n--- Multi-wallet poll ---")
            addresses = [w["address"] for w in TEST_WALLETS]
            new_swaps = await client.poll_wallets(addresses)
            total = sum(len(v) for v in new_swaps.values())
            logger.info("New swaps across all wallets: %d", total)

    except ValueError as e:
        logger.error("Config error: %s", e)
        logger.error("Make sure HELIUS_API_KEY is set in .env")
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        raise

    logger.info("\n" + "=" * 60)
    logger.info("Week 1 Test Complete ✓")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
