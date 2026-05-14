import pytest
from backend.scoring.launch_scorer import LaunchScorer, TokenMetrics


class TestLaunchScorer:
    def setup_method(self):
        self.scorer = LaunchScorer(min_score=50)

    def test_high_quality_token(self):
        """A strong token should score above threshold."""
        metrics = TokenMetrics(
            volume_1h=10000,
            buy_txns=80,
            sell_txns=20,
            liquidity_usd=50000,
            age_seconds=120,
            top_10_holder_pct=25,
            rugcheck_safe=True,
            mint_authority=False,
            freeze_authority=False,
            lp_locked=True
        )
        score = self.scorer.score(metrics)
        assert score is not None
        assert score >= 50

    def test_low_quality_token(self):
        """A weak token should score below threshold."""
        metrics = TokenMetrics(
            volume_1h=100,
            buy_txns=10,
            sell_txns=10,
            liquidity_usd=1000,
            age_seconds=600,
            top_10_holder_pct=60,
            rugcheck_safe=False,
            mint_authority=False,
            freeze_authority=False,
            lp_locked=False
        )
        score = self.scorer.score(metrics)
        assert score is None or score < 50

    def test_mint_authority_flag(self):
        """Token with mint authority should be rejected."""
        metrics = TokenMetrics(
            mint_authority=True
        )
        score = self.scorer.score(metrics)
        assert score is None

    def test_freeze_authority_flag(self):
        """Token with freeze authority should be rejected."""
        metrics = TokenMetrics(
            freeze_authority=True
        )
        score = self.scorer.score(metrics)
        assert score is None

    def test_high_holder_concentration(self):
        """Token with >50% top 10 holders should be rejected."""
        metrics = TokenMetrics(
            top_10_holder_pct=60,
            mint_authority=False,
            freeze_authority=False
        )
        score = self.scorer.score(metrics)
        assert score is None

    def test_score_breakdown(self):
        """Score breakdown should show all components."""
        metrics = TokenMetrics(
            volume_1h=10000,
            buy_txns=80,
            sell_txns=20,
            liquidity_usd=50000,
            age_seconds=120,
            top_10_holder_pct=25,
            rugcheck_safe=True,
            mint_authority=False,
            freeze_authority=False,
            lp_locked=True
        )
        breakdown = self.scorer.get_score_breakdown(metrics)
        assert breakdown["passed_safety"] is True
        assert "volume_bonus" in breakdown
        assert "buy_pressure_bonus" in breakdown
        assert "liquidity_bonus" in breakdown
        assert "age_bonus" in breakdown
        assert "holder_bonus" in breakdown

    def test_exact_score_calculation(self):
        """Verify exact score calculation for a known token."""
        metrics = TokenMetrics(
            volume_1h=10000,      # +25
            buy_txns=70,          # +20 (70/80 = 87.5% > 65%)
            sell_txns=10,
            liquidity_usd=50000,  # +15
            age_seconds=120,      # +15
            top_10_holder_pct=25, # +10
            rugcheck_safe=True,   # +15
            mint_authority=False,
            freeze_authority=False,
            lp_locked=True
        )
        score = self.scorer.score(metrics)
        assert score == 100  # All bonuses maxed out
