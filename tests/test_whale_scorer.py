import pytest
from datetime import datetime, timedelta
from backend.scoring.whale_scorer import WhaleScorer, Position


class TestWhaleScorer:
    def setup_method(self):
        self.scorer = WhaleScorer()

    @pytest.mark.asyncio
    async def test_new_wallet_score(self):
        """New wallets should get a neutral score of 50."""
        score = await self.scorer.calculate_wallet_score("new_wallet_123")
        assert score == 50.0

    @pytest.mark.asyncio
    async def test_position_tracking(self):
        """Should be able to track and close positions."""
        wallet = "whale_abc"
        token = "TOKEN123"
        now = datetime.utcnow()

        # Open position
        pos = await self.scorer.update_position(
            wallet=wallet,
            token_mint=token,
            buy_price_sol=10.0,
            buy_amount=100.0,
            timestamp=now
        )
        assert pos.status == "open"
        assert pos.token_mint == token

        # Close position with profit
        pnl = await self.scorer.close_position(
            wallet=wallet,
            token_mint=token,
            sell_price_sol=15.0,
            sell_timestamp=now + timedelta(hours=1)
        )
        assert pnl == 500.0  # (15 - 10) * 100

    @pytest.mark.asyncio
    async def test_win_rate_calculation(self):
        """Win rate should be calculated correctly."""
        wallet = "whale_win"
        now = datetime.utcnow()

        # 3 winning trades
        for i in range(3):
            await self.scorer.update_position(wallet, f"WIN{i}", 10.0, 10.0, now)
            await self.scorer.close_position(wallet, f"WIN{i}", 15.0, now + timedelta(hours=1))

        # 1 losing trade
        await self.scorer.update_position(wallet, "LOSE", 10.0, 10.0, now)
        await self.scorer.close_position(wallet, "LOSE", 5.0, now + timedelta(hours=1))

        stats = self.scorer._compute_stats(wallet)
        assert stats.win_rate == 0.75
        assert stats.total_trades == 4

    @pytest.mark.asyncio
    async def test_score_range(self):
        """Score should always be between 0 and 100."""
        wallet = "whale_range"
        now = datetime.utcnow()

        # Many winning trades
        for i in range(20):
            await self.scorer.update_position(wallet, f"TOK{i}", 10.0, 10.0, now - timedelta(days=i))
            await self.scorer.close_position(wallet, f"TOK{i}", 20.0, now - timedelta(days=i) + timedelta(hours=1))

        score = await self.scorer.calculate_wallet_score(wallet)
        assert 0 <= score <= 100

    @pytest.mark.asyncio
    async def test_wallet_summary(self):
        """Summary should include all key metrics."""
        wallet = "whale_summary"
        now = datetime.utcnow()

        await self.scorer.update_position(wallet, "TOK1", 10.0, 10.0, now)
        await self.scorer.close_position(wallet, "TOK1", 20.0, now + timedelta(hours=1))

        summary = await self.scorer.get_wallet_summary(wallet)
        assert "address" in summary
        assert "score" in summary
        assert "win_rate" in summary
        assert "avg_pnl_sol" in summary
        assert "total_trades" in summary

    @pytest.mark.asyncio
    async def test_memory_limit(self):
        """Should not store more than MAX_POSITIONS_PER_WALLET positions."""
        wallet = "whale_memory"
        now = datetime.utcnow()

        for i in range(600):
            await self.scorer.update_position(wallet, f"TOK{i}", 1.0, 1.0, now)

        assert len(self.scorer.positions[wallet]) == WhaleScorer.MAX_POSITIONS_PER_WALLET
