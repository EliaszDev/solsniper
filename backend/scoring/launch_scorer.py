from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class TokenMetrics:
    volume_1h: float = 0.0
    buy_txns: int = 0
    sell_txns: int = 0
    liquidity_usd: float = 0.0
    price_change_1h: float = 0.0
    age_seconds: float = 0.0
    top_10_holder_pct: float = 0.0
    rugcheck_safe: bool = True
    mint_authority: bool = False
    freeze_authority: bool = False
    lp_locked: bool = False


class LaunchScorer:
    """Scores new token launches based on early metrics and safety signals."""

    def __init__(self, min_score: int = 50):
        self.min_score = min_score

    def score(self, metrics: TokenMetrics) -> Optional[int]:
        """
        Calculate launch score (0-100) for a token.
        Returns None if token fails safety checks or minimum threshold.
        """
        if not self._pass_safety_checks(metrics):
            return None

        score = 0

        if metrics.volume_1h > 5000:
            score += 25

        total_txns = metrics.buy_txns + metrics.sell_txns
        if total_txns > 0:
            buy_ratio = metrics.buy_txns / total_txns
            if buy_ratio > 0.65:
                score += 20

        if metrics.liquidity_usd > 10000:
            score += 15

        if metrics.age_seconds < 300:
            score += 15

        if metrics.rugcheck_safe:
            score += 15

        if metrics.top_10_holder_pct < 40:
            score += 10

        return score if score >= self.min_score else None

    def _pass_safety_checks(self, metrics: TokenMetrics) -> bool:
        """Run safety checks. Return False if HIGH RISK flags detected."""
        if metrics.mint_authority:
            return False

        if metrics.freeze_authority:
            return False

        if metrics.top_10_holder_pct > 50:
            return False

        return True

    def get_score_breakdown(self, metrics: TokenMetrics) -> dict:
        """Get detailed score breakdown for a token."""
        safe = self._pass_safety_checks(metrics)
        score = self.score(metrics) or 0

        total_txns = metrics.buy_txns + metrics.sell_txns
        buy_ratio = (metrics.buy_txns / total_txns * 100) if total_txns > 0 else 0

        return {
            "total_score": score,
            "passed_safety": safe,
            "volume_bonus": 25 if metrics.volume_1h > 5000 else 0,
            "buy_pressure_bonus": 20 if buy_ratio > 65 else 0,
            "liquidity_bonus": 15 if metrics.liquidity_usd > 10000 else 0,
            "age_bonus": 15 if metrics.age_seconds < 300 else 0,
            "rugcheck_bonus": 15 if metrics.rugcheck_safe else 0,
            "holder_bonus": 10 if metrics.top_10_holder_pct < 40 else 0,
            "min_threshold": self.min_score,
            "qualified": score >= self.min_score
        }
