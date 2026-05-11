"""DexScreener API wrapper — async token data with built-in rate limiting."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from solders.pubkey import Pubkey

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class TokenPairData:
    mint: str
    price_usd: float
    liquidity_usd: float
    volume_h1: float
    volume_h6: float
    volume_h24: float
    txns_buys_h1: int
    txns_sells_h1: int
    price_change_h1: float
    price_change_h24: float
    pair_created_at: Optional[datetime]
    market_cap: Optional[float]
    dex_id: str
    url: str


# ---------------------------------------------------------------------------
# Address validation helper
# ---------------------------------------------------------------------------
def _validate_mint(mint: str) -> str:
    """Validate a Solana base-58 token mint. Returns the mint or raises ValueError."""
    if not mint or len(mint) > 44:
        raise ValueError(f"Invalid mint length: {mint!r}")
    try:
        Pubkey.from_string(mint)
    except Exception as exc:
        raise ValueError(f"Invalid base58 Solana mint: {mint!r}") from exc
    return mint


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class DexScreenerClient:
    """Async DexScreener client with ~3 req/s internal rate limit."""

    BASE = "https://api.dexscreener.com/latest"

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._last_request: float = 0.0
        self._min_interval: float = 0.34  # ~3 req/s

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "DexScreenerClient":
        await self._ensure_client()
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    async def _rate_limited_get(self, url: str) -> Dict[str, Any]:
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_request = asyncio.get_event_loop().time()

        client = await self._ensure_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "DexScreener HTTP %s: %s", exc.response.status_code, exc.response.text
            )
            raise
        except Exception as exc:
            logger.error("DexScreener request failed: %s", exc)
            raise

    # -------------------------------------------------------------------
    # Token data
    # -------------------------------------------------------------------
    @staticmethod
    def _parse_pair(pair: Dict[str, Any], mint: str) -> TokenPairData:
        vol = pair.get("volume", {})
        txns = pair.get("txns", {}).get("h1", {})
        price_change = pair.get("priceChange", {})
        created_raw = pair.get("pairCreatedAt")

        return TokenPairData(
            mint=mint,
            price_usd=float(pair.get("priceUsd", 0)),
            liquidity_usd=float(pair.get("liquidity", {}).get("usd", 0)),
            volume_h1=float(vol.get("h1", 0)),
            volume_h6=float(vol.get("h6", 0)),
            volume_h24=float(vol.get("h24", 0)),
            txns_buys_h1=int(txns.get("buys", 0)),
            txns_sells_h1=int(txns.get("sells", 0)),
            price_change_h1=float(price_change.get("h1", 0)),
            price_change_h24=float(price_change.get("h24", 0)),
            pair_created_at=(
                datetime.utcfromtimestamp(created_raw / 1000) if created_raw else None
            ),
            market_cap=pair.get("marketCap"),
            dex_id=pair.get("dexId", ""),
            url=pair.get("url", ""),
        )

    async def get_token_data(self, mint: str) -> Optional[TokenPairData]:
        """Fetch highest-liquidity pair for a token mint."""
        _validate_mint(mint)
        url = f"{self.BASE}/tokens/{mint}"
        data = await self._rate_limited_get(url)
        pairs = data.get("pairs", [])
        if not pairs:
            logger.warning("No DexScreener pairs for %s", mint[:8])
            return None

        best = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
        return self._parse_pair(best, mint)

    async def get_multiple_tokens(
        self, mints: List[str]
    ) -> Dict[str, Optional[TokenPairData]]:
        """Sequential batch fetch (respects rate limit)."""
        results: Dict[str, Optional[TokenPairData]] = {}
        for mint in mints:
            try:
                _validate_mint(mint)
                results[mint] = await self.get_token_data(mint)
            except Exception as exc:
                logger.warning("DexScreener error for %s: %s", mint[:8], exc)
                results[mint] = None
        return results
