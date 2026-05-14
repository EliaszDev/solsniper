import asyncio
import math
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class Position:
    token_mint: str
    buy_price_sol: float
    buy_amount: float
    timestamp: datetime
    sell_price_sol: Optional[float] = None
    sell_timestamp: Optional[datetime] = None
    realized_pnl: Optional[float] = None
    status: str = "open"


@dataclass
class WalletStats:
    address: str
    total_trades: int = 0
    profitable_trades: int = 0
    total_pnl_sol: float = 0.0
    avg_pnl_sol: float = 0.0
    win_rate: float = 0.0
    last_seen: Optional[datetime] = None
    score: float = 50.0


class WhaleScorer:
    """Scores tracked whale wallets based on historical performance.

    Thread-safe for async usage. Limits in-memory history to prevent
    unbounded memory growth.
    """

    MAX_POSITIONS_PER_WALLET = 500

    def __init__(self):
        self.positions: Dict[str, List[Position]] = {}
        self.wallet_stats: Dict[str, WalletStats] = {}
        self._lock = asyncio.Lock()

    async def update_position(self, wallet: str, token_mint: str, buy_price_sol: float,
                        buy_amount: float, timestamp: datetime) -> Position:
        """Record a new buy position for a wallet."""
        async with self._lock:
            if wallet not in self.positions:
                self.positions[wallet] = []

            position = Position(
                token_mint=token_mint,
                buy_price_sol=buy_price_sol,
                buy_amount=buy_amount,
                timestamp=timestamp
            )
            self.positions[wallet].append(position)

            # Prune old positions to prevent unbounded memory growth
            if len(self.positions[wallet]) > self.MAX_POSITIONS_PER_WALLET:
                self.positions[wallet] = self.positions[wallet][-self.MAX_POSITIONS_PER_WALLET:]

            return position

    async def close_position(self, wallet: str, token_mint: str, sell_price_sol: float,
                       sell_timestamp: datetime) -> Optional[float]:
        """Close an open position and calculate realized P&L."""
        async with self._lock:
            if wallet not in self.positions:
                return None

            for position in self.positions[wallet]:
                if position.token_mint == token_mint and position.status == "open":
                    position.sell_price_sol = sell_price_sol
                    position.sell_timestamp = sell_timestamp
                    position.realized_pnl = (sell_price_sol - position.buy_price_sol) * position.buy_amount
                    position.status = "closed"
                    return position.realized_pnl

            return None

    async def calculate_wallet_score(self, wallet: str) -> float:
        """Calculate composite wallet score (0-100)."""
        async with self._lock:
            if wallet not in self.positions or not self.positions[wallet]:
                return 50.0

            stats = self._compute_stats(wallet)

            if stats.total_trades == 0:
                return 50.0

            win_rate = stats.profitable_trades / stats.total_trades
            avg_pnl = stats.avg_pnl_sol

            recency_score = self._compute_recency_score(wallet)
            frequency_score = self._compute_frequency_score(wallet)

            score = (
                win_rate * 40 +
                min(max(avg_pnl * 10, -30), 30) * 0.3 +
                recency_score * 20 +
                frequency_score * 10
            )

            return min(max(score, 0), 100)

    def _compute_stats(self, wallet: str) -> WalletStats:
        """Compute basic wallet statistics."""
        if wallet not in self.wallet_stats:
            self.wallet_stats[wallet] = WalletStats(address=wallet)

        positions = self.positions.get(wallet, [])
        closed = [p for p in positions if p.status == "closed"]

        if not closed:
            return self.wallet_stats[wallet]

        profitable = [p for p in closed if p.realized_pnl and p.realized_pnl > 0]
        total_pnl = sum(p.realized_pnl for p in closed if p.realized_pnl)

        stats = WalletStats(
            address=wallet,
            total_trades=len(closed),
            profitable_trades=len(profitable),
            total_pnl_sol=total_pnl,
            avg_pnl_sol=total_pnl / len(closed),
            win_rate=len(profitable) / len(closed),
            last_seen=max((p.sell_timestamp for p in closed if p.sell_timestamp), default=None)
        )

        self.wallet_stats[wallet] = stats
        return stats

    def _compute_recency_score(self, wallet: str) -> float:
        """Compute recency score (0-1) based on last activity."""
        stats = self.wallet_stats.get(wallet)
        if not stats or not stats.last_seen:
            return 0.0

        days_since = (datetime.utcnow() - stats.last_seen).total_seconds() / 86400
        return math.exp(-days_since / 7)

    def _compute_frequency_score(self, wallet: str) -> float:
        """Compute trade frequency score (0-1)."""
        positions = self.positions.get(wallet, [])
        closed = [p for p in positions if p.status == "closed"]

        if not closed:
            return 0.0

        trades_per_week = len(closed) / max(len(closed), 1)
        return min(trades_per_week / 10, 1.0)

    async def get_wallet_summary(self, wallet: str) -> dict:
        """Get full wallet summary with score and stats."""
        async with self._lock:
            stats = self._compute_stats(wallet)

        score = await self.calculate_wallet_score(wallet)

        return {
            "address": wallet,
            "score": round(score, 2),
            "win_rate": round(stats.win_rate * 100, 2),
            "avg_pnl_sol": round(stats.avg_pnl_sol, 4),
            "total_trades": stats.total_trades,
            "profitable_trades": stats.profitable_trades,
            "last_seen": stats.last_seen.isoformat() if stats.last_seen else None
        }
