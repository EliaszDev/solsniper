"""Jupiter swap API wrapper — quote, build, sign, submit, confirm."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid
from typing import Any, Dict, Optional

import httpx
from solders.keypair import Keypair
from solders.transaction import Transaction

from backend.config import get_settings

logger = logging.getLogger(__name__)

_SOL_MINT = "So11111111111111111111111111111111111111112"
_SOL_DECIMALS = 9


class JupiterClient:
    """
    Full Jupiter v6 swap pipeline:
      1. get_quote     – USD amount → SOL → Jupiter quote
      2. build_swap_tx – quote → base64 unsigned transaction
      3. sign_tx       – base64 tx → signed bytes (uses WALLET_PRIVATE_KEY)
      4. submit_tx     – signed bytes → on-chain signature via Helius RPC
      5. confirm_tx    – poll RPC until confirmed / timeout
      6. execute_swap  – orchestrate 1-5 (respects PAPER_TRADING flag)
    """

    def __init__(self) -> None:
        self.cfg = get_settings()
        self._client: Optional[httpx.AsyncClient] = None
        self._keypair: Optional[Keypair] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "JupiterClient":
        await self._ensure_client()
        return self

    async def __aexit__(self, *_) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Keypair (lazy load)
    # ------------------------------------------------------------------
    def _load_keypair(self) -> Keypair:
        """Load wallet keypair from env. Raises if missing."""
        if self._keypair is not None:
            return self._keypair
        pk = self.cfg.WALLET_PRIVATE_KEY
        if pk is None:
            raise RuntimeError(
                "WALLET_PRIVATE_KEY not configured — required for live signing"
            )
        self._keypair = Keypair.from_base58_string(pk.get_secret_value())
        return self._keypair

    # ==================================================================
    # STEP 1 — Get a Quote
    # ==================================================================
    async def get_quote(self, token_mint: str, amount_usd: float) -> Dict[str, Any]:
        """
        Fetch a Jupiter swap quote buying *token_mint* with *amount_usd* worth of SOL.

        Flow:
          1. SOL/USD price from DexScreener (SOL mint)
          2. USD → SOL → lamports
          3. Jupiter /quote endpoint
        """
        sol_price = await self._fetch_sol_price_usd()
        if sol_price <= 0:
            raise RuntimeError(f"Invalid SOL price from DexScreener: {sol_price}")

        sol_amount = amount_usd / sol_price
        lamports = int(sol_amount * (10 ** _SOL_DECIMALS))

        if lamports <= 0:
            raise ValueError(f"Amount too small: ${amount_usd} → {lamports} lamports")

        url = (
            f"{self.cfg.JUPITER_QUOTE_URL}/quote"
            f"?inputMint={_SOL_MINT}"
            f"&outputMint={token_mint}"
            f"&amount={lamports}"
            f"&slippageBps={self.cfg.SLIPPAGE_BPS}"
        )

        client = await self._ensure_client()
        resp = await client.get(url)
        resp.raise_for_status()
        quote = resp.json()

        if "outAmount" not in quote:
            raise RuntimeError(f"Jupiter quote missing 'outAmount': {quote}")

        logger.info(
            "Jupiter quote: $%.2f → %s lamports → outAmount=%s",
            amount_usd, lamports, quote.get("outAmount"),
        )
        return quote

    async def _fetch_sol_price_usd(self) -> float:
        """Fetch SOL/USD from DexScreener (highest-liquidity pair)."""
        url = f"https://api.dexscreener.com/latest/dex/tokens/{_SOL_MINT}"
        client = await self._ensure_client()
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        pairs = data.get("pairs", [])
        if not pairs:
            raise RuntimeError("DexScreener returned no SOL pairs")
        best = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
        price = float(best.get("priceUsd", 0))
        if price <= 0:
            raise RuntimeError(f"Invalid SOL price from DexScreener: {price}")
        return price

    # ==================================================================
    # STEP 2 — Build Swap Transaction
    # ==================================================================
    async def build_swap_tx(self, quote: Dict[str, Any], wallet_pubkey: str) -> str:
        """
        Turn a Jupiter quote into a base64-encoded unsigned transaction.
        """
        url = f"{self.cfg.JUPITER_QUOTE_URL}/swap"
        payload = {
            "quoteResponse": quote,
            "userPublicKey": wallet_pubkey,
            "wrapAndUnwrapSol": True,
            "dynamicComputeUnitLimit": True,
            "prioritizationFeeLamports": 1000,
        }

        client = await self._ensure_client()
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        tx_b64 = data.get("swapTransaction")
        if not tx_b64:
            raise RuntimeError(f"Jupiter swap response missing 'swapTransaction': {data}")

        logger.info("Built swap tx (base64 len=%d)", len(tx_b64))
        return tx_b64

    # ==================================================================
    # STEP 3 — Sign Transaction
    # ==================================================================
    def sign_tx(self, base64_tx: str) -> bytes:
        """
        Sign a base64-encoded transaction (legacy or v0) with the wallet keypair.
        Returns the serialized signed transaction bytes.
        """
        keypair = self._load_keypair()
        raw = base64.b64decode(base64_tx)
        tx = Transaction.from_bytes(raw)
        tx.sign([keypair], tx.message.recent_blockhash)
        signed_bytes = bytes(tx)
        logger.info("Signed tx (len=%d bytes)", len(signed_bytes))
        return signed_bytes

    # ==================================================================
    # STEP 4 — Submit + Confirm Transaction
    # ==================================================================
    async def submit_tx(self, signed_bytes: bytes) -> str:
        """
        Send a signed transaction to the Solana network via Helius RPC.
        Returns the transaction signature string.
        """
        # Paper-trading guard: return fake signature without hitting RPC
        if self.cfg.PAPER_TRADING:
            fake_sig = f"PAPER_{uuid.uuid4().hex[:32]}"
            logger.info("PAPER_TRADING=True — returning fake signature %s", fake_sig)
            return fake_sig

        b64_signed = base64.b64encode(signed_bytes).decode("ascii")
        rpc_url = self.cfg.helius_rpc_url

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "sendTransaction",
            "params": [
                b64_signed,
                {
                    "encoding": "base64",
                    "maxRetries": 3,
                    "skipPreflight": False,
                },
            ],
        }

        client = await self._ensure_client()
        resp = await client.post(rpc_url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            raise RuntimeError(f"RPC sendTransaction error: {data['error']}")

        signature = data.get("result")
        if not signature:
            raise RuntimeError(f"RPC sendTransaction returned empty result: {data}")

        logger.info("Transaction submitted — signature: %s", signature)
        return signature

    async def confirm_tx(self, signature: str, timeout_seconds: int = 30) -> bool:
        """
        Poll RPC getSignatureStatuses until the tx reaches 'confirmed' or 'finalized'.
        Returns True on confirmation, False on timeout.
        """
        # Paper-trading: always "confirmed"
        if signature.startswith("PAPER_"):
            logger.info("PAPER signature — skipping on-chain confirmation")
            return True

        rpc_url = self.cfg.helius_rpc_url
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        poll_interval = 2.0

        while asyncio.get_event_loop().time() < deadline:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignatureStatuses",
                "params": [[signature], {"searchTransactionHistory": True}],
            }

            client = await self._ensure_client()
            resp = await client.post(rpc_url, json=payload)
            resp.raise_for_status()
            data = resp.json()

            result = data.get("result", {})
            values = result.get("value", [])
            if not values:
                logger.debug("Signature %s not yet seen by RPC", signature[:16])
                await asyncio.sleep(poll_interval)
                continue

            status_info = values[0]
            if status_info is None:
                await asyncio.sleep(poll_interval)
                continue

            err = status_info.get("err")
            if err:
                logger.error("Transaction %s failed on-chain: %s", signature[:16], err)
                return False

            confirmation = status_info.get("confirmationStatus")
            if confirmation in ("confirmed", "finalized"):
                logger.info(
                    "Transaction %s confirmed (status=%s)",
                    signature[:16], confirmation,
                )
                return True

            slot = status_info.get("slot", "?")
            logger.debug(
                "Tx %s — slot=%s, status=%s", signature[:16], slot, confirmation
            )
            await asyncio.sleep(poll_interval)

        logger.warning("Transaction %s confirmation timed out after %ds", signature[:16], timeout_seconds)
        return False

    # ==================================================================
    # STEP 5 — Full execute_swap Orchestration
    # ==================================================================
    async def execute_swap(
        self,
        token_mint: str,
        amount_usd: float,
        wallet_pubkey: str,
    ) -> Dict[str, Any]:
        """
        End-to-end swap: quote → build → sign → submit → confirm.

        Returns dict:
        {
            "success": bool,
            "signature": str,
            "token_mint": str,
            "amount_usd": float,
            "out_amount": str,   # raw outAmount from Jupiter quote
            "error": str | None,
        }
        """
        try:
            quote = await self.get_quote(token_mint, amount_usd)
            base64_tx = await self.build_swap_tx(quote, wallet_pubkey)
            signed = self.sign_tx(base64_tx)
            signature = await self.submit_tx(signed)
            confirmed = await self.confirm_tx(signature)

            return {
                "success": confirmed,
                "signature": signature,
                "token_mint": token_mint,
                "amount_usd": amount_usd,
                "out_amount": str(quote.get("outAmount", "")),
                "error": None,
            }

        except Exception as exc:
            logger.exception("execute_swap failed for %s", token_mint)
            return {
                "success": False,
                "signature": "",
                "token_mint": token_mint,
                "amount_usd": amount_usd,
                "out_amount": "",
                "error": str(exc),
            }
