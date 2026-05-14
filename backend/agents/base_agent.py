import json
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseAgent(ABC):
    """Base class for SolSniper agents powered by Kimi K2."""

    def __init__(self, api_key: str, api_base: str = "https://api.moonshot.cn/v1", model: str = "kimi-k2"):
        self.api_key = api_key
        self.api_base = api_base
        self.model = model

    @abstractmethod
    async def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze context and return structured recommendation."""
        pass

    def _build_prompt(self, template: str, context: Dict[str, Any]) -> str:
        """Build prompt from template and context variables.

        Uses manual regex substitution instead of str.format() to prevent
        prompt injection attacks via curly braces in user-controlled data.
        """
        prompt = template
        for key, value in context.items():
            # Sanitize: strip curly braces to prevent nested substitution attacks
            safe_value = str(value).replace("{", "[").replace("}", "]")
            prompt = re.sub(rf"\{{{re.escape(key)}\}}", safe_value, prompt)
        return prompt

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM response into structured JSON.

        Truncates to max 4KB before parsing to prevent memory exhaustion.
        """
        truncated = response_text[:4096]
        try:
            return json.loads(truncated)
        except json.JSONDecodeError:
            return {
                "recommendation": "HOLD",
                "confidence": 0,
                "reasoning": "Failed to parse agent response",
                "raw_response": truncated
            }

    def _format_reasoning(self, reasoning: str, max_length: int = 200) -> str:
        """Format reasoning text to specified length."""
        if len(reasoning) > max_length:
            return reasoning[:max_length - 3] + "..."
        return reasoning
