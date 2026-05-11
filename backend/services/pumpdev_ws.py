"""PumpDev websocket listener — new token launches."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Optional

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class NewTokenEvent:
    mint: str
    name: str
    symbol: str
    creator: str
    initial_buy_sol: float
    market_cap_sol: float
    metadata_uri: Optional[str]


# ---------------------------------------------------------------------------
# Listener
# ---------------------------------------------------------------------------
class PumpDevListener:
    """WebSocket listener for PumpDev new token launches with auto-reconnect."""

    WS_URL = "wss://pumpdev.io/ws"
    RECONNECT_BACKOFF_BASE = 5.0
    RECONNECT_BACKOFF_MAX = 60.0

    def __init__(
        self,
        on_token: Callable[[NewTokenEvent], Coroutine[Any, Any, None]],
    ) -> None:
        self.on_token = on_token
        self._running = False
        self._task: Optional[asyncio.Task] = None

    # -------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------
    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._listen_loop())
        logger.info("PumpDev listener started")

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("PumpDev listener stopped")

    # -------------------------------------------------------------------
    # Connection loop
    # -------------------------------------------------------------------
    async def _listen_loop(self) -> None:
        backoff = self.RECONNECT_BACKOFF_BASE
        while self._running:
            try:
                await self._connect_and_read()
                backoff = self.RECONNECT_BACKOFF_BASE  # reset on clean exit
            except ConnectionClosed:
                logger.warning("PumpDev WS closed, reconnecting in %.0fs…", backoff)
            except Exception as exc:
                logger.error("PumpDev WS error: %s — reconnecting in %.0fs…", exc, backoff)

            if not self._running:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, self.RECONNECT_BACKOFF_MAX)

    async def _connect_and_read(self) -> None:
        async with websockets.connect(self.WS_URL) as ws:
            # subscribe
            await ws.send(json.dumps({"method": "subscribeNewToken"}))
            async for raw in ws:
                if not self._running:
                    break
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                # skip heartbeat / ack
                if msg.get("type") in ("heartbeat", "ack"):
                    continue

                event = self._parse_new_token(msg)
                if event:
                    asyncio.create_task(self._safe_callback(event))

    async def _safe_callback(self, event: NewTokenEvent) -> None:
        try:
            await self.on_token(event)
        except Exception as exc:
            logger.error("PumpDev on_token callback error: %s", exc)

    # -------------------------------------------------------------------
    # Parsing
    # -------------------------------------------------------------------
    @staticmethod
    def _parse_new_token(msg: dict) -> Optional[NewTokenEvent]:
        data = msg.get("data") or msg
        mint = data.get("mint")
        if not mint:
            return None
        return NewTokenEvent(
            mint=mint,
            name=data.get("name", ""),
            symbol=data.get("symbol", ""),
            creator=data.get("creator", ""),
            initial_buy_sol=float(data.get("initialBuySol", 0)),
            market_cap_sol=float(data.get("marketCapSol", 0)),
            metadata_uri=data.get("metadataUri"),
        )
