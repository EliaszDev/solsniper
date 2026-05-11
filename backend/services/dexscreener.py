"""DexScreener REST API client."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"


@dataclass
class TokenPairData:
    """Enriched token data from DexScreener."""
    mint: str
    symbol: str
    name: str
    price_usd: float
    liquidity_usd: float
    volume_h1: float
    volume_h6: float
    volume_h24: float
    txns_h1_buys: int
    txns_h1_sells: int
    price_change_h1: float
    price_change_h24: float
    pair_created_at: int  # unix timestamp
    market_cap: float
    url: str
    dex_id: str


class DexScreenerClient:
    """Async DexScreener API client with basic rate-limit handling."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._last_request_time: float = 0.0
        self._min_interval = 0.35  # ~3 req/s to stay under free limits

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=15.0)
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    # ── public API ──────────────────────────────────────────────

    async def get_token_data(self, mint: str) -> Optional[TokenPairData]:
        """Fetch pair data for a single token mint."""
        await self._throttle()
        url = f"{DEXSCREENER_API}/tokens/{mint}"
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            data = resp.json()
            pairs = data.get("pairs", [])
            if not pairs:
                logger.warning("DexScreener: no pairs for %s", mint)
                return None
            # pick the pair with highest liquidity
            best = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
            return self._parse_pair(best, mint)
        except httpx.HTTPStatusError as e:
            logger.error("DexScreener HTTP %s for %s", e.response.status_code, mint)
            return None
        except Exception as e:
            logger.error("DexScreener error for %s: %s", mint, e)
            return None

    async def get_multiple_tokens(self, mints: list[str]) -> dict[str, Optional[TokenPairData]]:
        """Fetch data for multiple mints sequentially (rate-limited)."""
        results = {}
        for m in mints:
            results[m] = await self.get_token_data(m)
        return results

    # ── helpers ─────────────────────────────────────────────────

    def _parse_pair(self, pair: dict, mint: str) -> TokenPairData:
        vol = pair.get("volume", {})
        txns = pair.get("txns", {}).get("h1", {})
        liq = pair.get("liquidity", {})
        return TokenPairData(
            mint=mint,
            symbol=pair.get("baseToken", {}).get("symbol", "???"),
            name=pair.get("baseToken", {}).get("name", "???"),
            price_usd=float(pair.get("priceUsd", 0) or 0),
            liquidity_usd=float(liq.get("usd", 0) or 0),
            volume_h1=float(vol.get("h1", 0) or 0),
            volume_h6=float(vol.get("h6", 0) or 0),
            volume_h24=float(vol.get("h24", 0) or 0),
            txns_h1_buys=int(txns.get("buys", 0) or 0),
            txns_h1_sells=int(txns.get("sells", 0) or 0),
            price_change_h1=float(pair.get("priceChange", {}).get("h1", 0) or 0),
            price_change_h24=float(pair.get("priceChange", {}).get("h24", 0) or 0),
            pair_created_at=int(pair.get("pairCreatedAt", 0) or 0) // 1000,  # ms → s
            market_cap=float(pair.get("marketCap", 0) or 0),
            url=pair.get("url", ""),
            dex_id=pair.get("dexId", ""),
        )

    async def _throttle(self):
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()
