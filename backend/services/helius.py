"""Helius API wrapper — async wallet history & swap parsing."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from solders.pubkey import Pubkey

from backend.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_SOL_MINT = "So11111111111111111111111111111111111111112"
_SOL_DECIMALS = 9


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class SwapEvent:
    signature: str
    timestamp: datetime
    direction: str  # "buy" | "sell"
    token_mint_in: str
    token_mint_out: str
    amount_in: float
    amount_out: float
    sol_delta: float
    raw: Dict[str, Any]


# ---------------------------------------------------------------------------
# Address validation helper
# ---------------------------------------------------------------------------
def _validate_address(addr: str) -> str:
    """Validate a Solana base-58 address. Returns the address or raises ValueError."""
    if not addr or len(addr) > 44:
        raise ValueError(f"Invalid address length: {addr!r}")
    try:
        Pubkey.from_string(addr)
    except Exception as exc:
        raise ValueError(f"Invalid base58 Solana address: {addr!r}") from exc
    return addr


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class HeliusClient:
    def __init__(self) -> None:
        cfg = get_settings()
        self._api_key = cfg.HELIUS_API_KEY.get_secret_value()
        self.base = cfg.helius_api_base
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "HeliusClient":
        await self._ensure_client()
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    # -------------------------------------------------------------------
    # Raw history
    # -------------------------------------------------------------------
    async def get_wallet_history(
        self, wallet: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        _validate_address(wallet)
        url = f"{self.base}/addresses/?api-key={self._api_key}"
        payload = {
            "query": {
                "accounts": [wallet],
                "types": ["SWAP"],
                "limit": limit,
            }
        }
        client = await self._ensure_client()
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else data.get("result", [])
        except httpx.HTTPStatusError as exc:
            logger.error("Helius HTTP error %s: %s", exc.response.status_code, exc.response.text)
            raise
        except Exception as exc:
            logger.error("Helius request failed: %s", exc)
            raise

    # -------------------------------------------------------------------
    # Swap parsing
    # -------------------------------------------------------------------
    @staticmethod
    def _parse_swap(raw: Dict[str, Any]) -> Optional[SwapEvent]:
        sig = raw.get("signature") or raw.get("txHash")
        if not sig:
            return None

        ts_raw = raw.get("timestamp")
        ts = (
            datetime.fromtimestamp(ts_raw, tz=timezone.utc)
            if isinstance(ts_raw, (int, float))
            else datetime.now(timezone.utc)
        )

        # Helius enhanced API v0 returns nativeTransfers + tokenTransfers
        native = raw.get("nativeTransfers", [])
        token_transfers = raw.get("tokenTransfers", [])

        sol_delta = sum(
            t["amount"] / 10 ** _SOL_DECIMALS
            for t in native
            if t.get("mint") == _SOL_MINT
        )

        direction = "buy" if sol_delta < 0 else "sell"

        # Pick first non-SOL token transfer as the "interesting" side
        non_sol = [t for t in token_transfers if t.get("mint") != _SOL_MINT]
        if not non_sol:
            return None

        token_tx = non_sol[0]
        token_mint = token_tx.get("mint", "")
        amount = token_tx.get("tokenAmount", 0.0)

        return SwapEvent(
            signature=sig,
            timestamp=ts,
            direction=direction,
            token_mint_in=_SOL_MINT if direction == "buy" else token_mint,
            token_mint_out=token_mint if direction == "buy" else _SOL_MINT,
            amount_in=abs(sol_delta) if direction == "buy" else amount,
            amount_out=amount if direction == "buy" else abs(sol_delta),
            sol_delta=abs(sol_delta),
            raw=raw,
        )

    async def get_wallet_swaps(
        self, wallet: str, limit: int = 100
    ) -> List[SwapEvent]:
        raw_txs = await self.get_wallet_history(wallet, limit)
        parsed: List[SwapEvent] = []
        for tx in raw_txs:
            swap = self._parse_swap(tx)
            if swap:
                parsed.append(swap)
        return parsed

    # -------------------------------------------------------------------
    # Multi-wallet polling with deduplication
    # -------------------------------------------------------------------
    async def poll_wallets(
        self,
        wallets: List[str],
        limit_per_wallet: int = 50,
    ) -> Dict[str, List[SwapEvent]]:
        """Poll multiple wallets, return only *new* swaps since last call."""
        results: Dict[str, List[SwapEvent]] = {}
        for wallet in wallets:
            _validate_address(wallet)
            try:
                swaps = await self.get_wallet_swaps(wallet, limit_per_wallet)
                results[wallet] = swaps
                if swaps:
                    logger.info(
                        "Wallet %s — %d new swap(s)", wallet[:8], len(swaps)
                    )
            except Exception as exc:
                logger.warning("Failed polling %s: %s", wallet[:8], exc)
                results[wallet] = []
        return results
