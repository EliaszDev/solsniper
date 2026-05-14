from typing import Dict, Any
from .base_agent import BaseAgent


class SniperAgent(BaseAgent):
    """Agent that analyzes new token snipe opportunities."""

    SNIPER_PROMPT = """Context:
- Token: {name} ({symbol})
- Mint: {mint}
- Age: {age} seconds
- Launch score: {score}/100
- 1h Volume: ${volume_1h}
- Buy pressure: {buy_pct}% buys
- Liquidity: ${liquidity}
- Safety: {safety_status}
- Holder concentration: {concentration}%
- Creator wallet: {creator} (new wallet: {new_wallet})

Task: Is this worth sniping? If yes, suggest entry size (max $50), take-profit targets (multiple levels), stop-loss. Explain briefly.

Respond in valid JSON:
{{
  "recommendation": "SNIPE",
  "confidence": 65,
  "suggested_size_usd": 20,
  "take_profit_levels": [150, 300, 500],
  "stop_loss_pct": 50,
  "reasoning": "Strong early buy pressure with clean contract and growing liquidity. Small position justified; high risk/reward with layered TP targets."
}}"""

    async def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze token snipe opportunity and return recommendation."""
        prompt = self._build_prompt(self.SNIPER_PROMPT, context)

        # Mock response for now (replace with actual Kimi K2 API call)
        mock_response = {
            "recommendation": "SNIPE",
            "confidence": min(context.get("score", 50), 95),
            "suggested_size_usd": 20,
            "take_profit_levels": [150, 300, 500],
            "stop_loss_pct": 50,
            "reasoning": f"Launch score {context.get('score', 0)}/100."
        }

        if context.get("safety_status") != "CLEAN":
            mock_response.update({
                "recommendation": "REJECT",
                "confidence": 95,
                "reasoning": "Token failed safety checks. Skipping."
            })

        return {
            **mock_response,
            "type": "snipe",
            "token_mint": context.get("mint"),
            "token_symbol": context.get("symbol")
        }
