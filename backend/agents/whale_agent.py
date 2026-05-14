from typing import Dict, Any
from .base_agent import BaseAgent


class WhaleAgent(BaseAgent):
    """Agent that analyzes whale copy-trade opportunities."""

    WHALE_PROMPT = """Context:
- Token mint: {token_mint}
- Token symbol: {token_symbol}
- Whale wallet score: {wallet_score}/100
- Whale historical win rate: {win_rate}%
- Current token liquidity: ${liquidity}
- 1h price change: {price_change_1h}%
- RugCheck safety: {rugcheck_status}
- Top 10 holder concentration: {concentration}%

Task: Should I copy this trade? Propose entry size (max $50), take-profit target (%), stop-loss (%). Explain in 2 sentences.

Respond in valid JSON:
{{
  "recommendation": "BUY",
  "confidence": 78,
  "suggested_size_usd": 30,
  "take_profit_pct": 120,
  "stop_loss_pct": 40,
  "reasoning": "High-conviction whale with 73% win rate bought into a token with growing liquidity and no rug flags. Suggesting conservative $30 entry with 2x TP target."
}}"""

    async def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze whale trade opportunity and return recommendation."""
        prompt = self._build_prompt(self.WHALE_PROMPT, context)

        # Mock response for now (replace with actual Kimi K2 API call)
        # In production: response = await self._call_kimi(prompt)
        mock_response = {
            "recommendation": "BUY",
            "confidence": min(context.get("wallet_score", 50), 95),
            "suggested_size_usd": 30,
            "take_profit_pct": 120,
            "stop_loss_pct": 40,
            "reasoning": f"Whale with {context.get('win_rate', 0)}% win rate."
        }

        if context.get("rugcheck_status") == "flagged":
            mock_response.update({
                "recommendation": "REJECT",
                "confidence": 95,
                "reasoning": "Token has safety flags. Skipping."
            })

        return {
            **mock_response,
            "type": "whale_copy",
            "token_mint": context.get("token_mint"),
            "token_symbol": context.get("token_symbol"),
            "source_wallet": context.get("wallet_address")
        }
