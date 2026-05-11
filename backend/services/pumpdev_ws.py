"""PumpDev WebSocket listener — new token launches with auto-reconnect."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Callable, Optional

import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatusCode

logger = logging.getLogger(__name__)

PUMPDEV_WS = "wss://pumpdev.io/ws"
RECONNECT_DELAY = 5.0
MAX_RECONNECT_DELAY = 60.0


@dataclass
class NewTokenEvent:
    """Parsed new token launch event."""
    mint: str
    name: str
    symbol: str
    creator: str
    initial_buy_sol: float
    market_cap_sol: float
    metadata_uri: str
    raw: dict


class PumpDevListener:
    """Async WebSocket listener for PumpDev new-token events."""

    def __init__(self, on_token: Callable[[NewTokenEvent], asyncio.Future] | None = None):
        self.on_token = on_token
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._reconnect_delay = RECONNECT_DELAY

    async def start(self):
        """Start the listener in a background task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._listen_loop())
        logger.info("PumpDev listener started")

    async def stop(self):
        """Stop the listener gracefully."""
        self._running = False
        if self._ws:
            await self._ws.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("PumpDev listener stopped")

    # ── internals ───────────────────────────────────────────────

    async def _listen_loop(self):
        while self._running:
            try:
                await self._connect_and_listen()
                # successful run → reset backoff
                self._reconnect_delay = RECONNECT_DELAY
            except ConnectionClosed as e:
                logger.warning("PumpDev WS closed: %s", e)
            except InvalidStatusCode as e:
                logger.error("PumpDev WS status %s", e.status_code)
            except Exception as e:
                logger.error("PumpDev WS error: %s", e)

            if not self._running:
                break

            logger.info("PumpDev reconnecting in %.0fs...", self._reconnect_delay)
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(self._reconnect_delay * 1.5, MAX_RECONNECT_DELAY)

    async def _connect_and_listen(self):
        logger.info("PumpDev connecting to %s", PUMPDEV_WS)
        async with websockets.connect(PUMPDEV_WS) as ws:
            self._ws = ws
            # subscribe
            sub = {"method": "subscribeNewToken"}
            await ws.send(json.dumps(sub))
            logger.info("PumpDev subscribed to new tokens")

            async for message in ws:
                if not self._running:
                    break
                await self._handle_message(message)

    async def _handle_message(self, message: str):
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.warning("PumpDev: non-JSON message: %s", message[:200])
            return

        # PumpDev may wrap events differently — handle common shapes
        event = data.get("data", data)
        if not isinstance(event, dict):
            return

        # skip heartbeat / ack messages
        if "mint" not in event:
            return

        token = NewTokenEvent(
            mint=event.get("mint", ""),
            name=event.get("name", ""),
            symbol=event.get("symbol", ""),
            creator=event.get("creator", ""),
            initial_buy_sol=float(event.get("initialBuy", 0) or 0),
            market_cap_sol=float(event.get("marketCapSol", 0) or 0),
            metadata_uri=event.get("uri", ""),
            raw=event,
        )

        if not token.mint:
            return

        logger.info("PumpDev new token: %s (%s) mint=%s", token.name, token.symbol, token.mint)

        if self.on_token:
            try:
                await self.on_token(token)
            except Exception as e:
                logger.error("Error in on_token callback: %s", e)
