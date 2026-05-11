"""Helius API client — wallet history polling + swap parsing."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

HELIUS_API = "https://api.helius.xyz/v1"


@dataclass
class SwapEvent:
    """Parsed swap from Helius wallet history."""
    signature: str
    timestamp: int
    wallet: str
    direction: str      # 'buy' | 'sell'
    token_mint_in: str
    token_mint_out: str
    amount_in: float
    amount_out: float
    sol_delta: float    # negative = spent SOL (buy), positive = received SOL (sell)
    fee: float = 0.0
    raw: dict = field(default_factory=dict, repr=False)


class HeliusClient:
    """Async Helius API client."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.HELIUS_API_KEY
        if not self.api_key or self.api_key == "your_helius_key_here":
            raise ValueError("HELIUS_API_KEY not configured")
        self._client: Optional[httpx.AsyncClient] = None
        self._last_sig: dict[str, str] = {}   # wallet -> last seen signature

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    # ── public API ──────────────────────────────────────────────

    async def get_wallet_history(self, wallet: str, limit: int = 10) -> List[dict]:
        """Fetch recent SWAP transactions for a wallet."""
        url = (
            f"{HELIUS_API}/wallet/{wallet}/history"
            f"?api-key={self.api_key}&type=SWAP&limit={limit}"
        )
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except httpx.HTTPStatusError as e:
            logger.error("Helius HTTP %s for %s: %s", e.response.status_code, wallet, e)
            return []
        except Exception as e:
            logger.error("Helius error for %s: %s", wallet, e)
            return []

    async def get_wallet_swaps(self, wallet: str, limit: int = 10) -> List[SwapEvent]:
        """Fetch + parse SWAP transactions for a wallet."""
        raw_txs = await self.get_wallet_history(wallet, limit)
        swaps = []
        for tx in raw_txs:
            swap = self._parse_swap(tx, wallet)
            if swap:
                swaps.append(swap)
        return swaps

    async def poll_wallets(self, wallets: List[str]) -> dict[str, List[SwapEvent]]:
        """Poll multiple wallets and return only *new* swaps per wallet."""
        results: dict[str, List[SwapEvent]] = {}
        for w in wallets:
            swaps = await self.get_wallet_swaps(w, limit=20)
            # filter out already-seen signatures
            last = self._last_sig.get(w)
            new_swaps = []
            for s in swaps:
                if s.signature == last:
                    break
                new_swaps.append(s)
            if swaps:
                self._last_sig[w] = swaps[0].signature
            if new_swaps:
                results[w] = new_swaps
                logger.info("Wallet %s: %d new swap(s)", w, len(new_swaps))
        return results

    # ── helpers ─────────────────────────────────────────────────

    @staticmethod
    def _parse_swap(tx: dict, wallet: str) -> Optional[SwapEvent]:
        """Parse a raw Helius SWAP tx into SwapEvent."""
        sig = tx.get("signature")
        ts = tx.get("timestamp", 0)
        if not sig:
            return None

        # Helius v1 SWAP txs have tokenTransfers / balanceChanges
        transfers = tx.get("tokenTransfers", [])
        balance_changes = tx.get("balanceChanges", [])

        # find SOL delta for this wallet
        sol_delta = 0.0
        for bc in balance_changes:
            if bc.get("owner") == wallet and bc.get("mint") == "So11111111111111111111111111111111111111112":
                sol_delta = float(bc.get("amount", 0))
                break

        # infer direction from SOL delta: negative = spent SOL (buy), positive = received (sell)
        direction = "buy" if sol_delta < 0 else "sell"

        # find token mints in/out
        token_in = ""
        token_out = ""
        amount_in = 0.0
        amount_out = 0.0

        for t in transfers:
            if t.get("fromUserAccount") == wallet:
                # wallet is sending this token → it's the "in" token (what they give up)
                if not token_in:
                    token_in = t.get("mint", "")
                    amount_in = float(t.get("tokenAmount", 0))
            if t.get("toUserAccount") == wallet:
                # wallet is receiving this token → it's the "out" token (what they get)
                if not token_out:
                    token_out = t.get("mint", "")
                    amount_out = float(t.get("tokenAmount", 0))

        # fallback: if no token transfers, use native transfers
        if not token_in and not token_out:
            native = tx.get("nativeTransfers", [])
            for nt in native:
                if nt.get("fromUserAccount") == wallet:
                    token_in = "So11111111111111111111111111111111111111112"
                    amount_in = float(nt.get("amount", 0)) / 1e9
                if nt.get("toUserAccount") == wallet:
                    token_out = "So11111111111111111111111111111111111111112"
                    amount_out = float(nt.get("amount", 0)) / 1e9

        return SwapEvent(
            signature=sig,
            timestamp=ts,
            wallet=wallet,
            direction=direction,
            token_mint_in=token_in or "unknown",
            token_mint_out=token_out or "unknown",
            amount_in=amount_in,
            amount_out=amount_out,
            sol_delta=sol_delta,
            raw=tx,
        )
