import pytest
import asyncio
from backend.agents.whale_agent import WhaleAgent
from backend.agents.sniper_agent import SniperAgent


class TestWhaleAgent:
    def setup_method(self):
        self.agent = WhaleAgent(api_key="test_key")

    @pytest.mark.asyncio
    async def test_analyze_safe_token(self):
        """Should recommend BUY for safe token with good whale."""
        context = {
            "token_mint": "SAFE123",
            "token_symbol": "SAFE",
            "wallet_score": 80,
            "win_rate": 75,
            "liquidity": 50000,
            "price_change_1h": 15,
            "rugcheck_status": "safe",
            "concentration": 25,
            "wallet_address": "whale_abc"
        }
        result = await self.agent.analyze(context)
        assert result["recommendation"] == "BUY"
        assert result["type"] == "whale_copy"
        assert "suggested_size_usd" in result
        assert "take_profit_pct" in result

    @pytest.mark.asyncio
    async def test_analyze_flagged_token(self):
        """Should reject flagged token."""
        context = {
            "token_mint": "FLAG123",
            "token_symbol": "FLAG",
            "wallet_score": 80,
            "win_rate": 75,
            "liquidity": 50000,
            "price_change_1h": 15,
            "rugcheck_status": "flagged",
            "concentration": 25,
            "wallet_address": "whale_abc"
        }
        result = await self.agent.analyze(context)
        assert result["recommendation"] == "REJECT"
        assert result["confidence"] == 95


class TestSniperAgent:
    def setup_method(self):
        self.agent = SniperAgent(api_key="test_key")

    @pytest.mark.asyncio
    async def test_analyze_good_launch(self):
        """Should recommend SNIPE for good launch."""
        context = {
            "name": "MoonShot",
            "symbol": "MOON",
            "mint": "MOON123",
            "age": 60,
            "score": 85,
            "volume_1h": 15000,
            "buy_pct": 80,
            "liquidity": 30000,
            "safety_status": "CLEAN",
            "concentration": 20,
            "creator": "creator_abc",
            "new_wallet": "no"
        }
        result = await self.agent.analyze(context)
        assert result["recommendation"] == "SNIPE"
        assert result["type"] == "snipe"
        assert "take_profit_levels" in result

    @pytest.mark.asyncio
    async def test_analyze_unsafe_token(self):
        """Should reject unsafe token."""
        context = {
            "name": "RugPull",
            "symbol": "RUG",
            "mint": "RUG123",
            "age": 60,
            "score": 30,
            "volume_1h": 100,
            "buy_pct": 40,
            "liquidity": 1000,
            "safety_status": "FLAGGED",
            "concentration": 60,
            "creator": "creator_abc",
            "new_wallet": "yes"
        }
        result = await self.agent.analyze(context)
        assert result["recommendation"] == "REJECT"
