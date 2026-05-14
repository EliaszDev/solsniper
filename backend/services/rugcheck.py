import logging
from typing import Dict, Optional
import aiohttp

logger = logging.getLogger(__name__)


class RugCheckService:
    """Service for token safety checks via RugCheck.xyz and Solscan APIs."""

    RUGCHECK_API = "https://api.rugcheck.xyz/v1/tokens/{mint}/report"
    SOLSCAN_API = "https://public-api.solscan.io/token/holders"

    def __init__(self, solscan_api_key: Optional[str] = None):
        self.solscan_api_key = solscan_api_key
        self.timeout = aiohttp.ClientTimeout(total=10)

    async def check_token(self, token_mint: str) -> Dict[str, any]:
        """Run full safety check on a token.

        Fails closed — if safety APIs are unreachable, the token is marked unsafe.
        Returns dict with:
        - safe: bool (overall safety)
        - flags: list of flagged issues
        - mint_authority: bool
        - freeze_authority: bool
        - lp_locked: bool
        - top10_holder_pct: float
        - risk_level: str (LOW/MEDIUM/HIGH)
        - api_errors: list of error descriptions
        """
        result = {
            "safe": False,
            "flags": [],
            "mint_authority": False,
            "freeze_authority": False,
            "lp_locked": False,
            "top10_holder_pct": 0.0,
            "risk_level": "HIGH",
            "api_errors": []
        }

        rugcheck_ok = await self._check_rugcheck(token_mint, result)
        solscan_ok = await self._check_solscan(token_mint, result)

        if not rugcheck_ok or not solscan_ok:
            result["api_errors"].append(
                f"RugCheck OK: {rugcheck_ok}, Solscan OK: {solscan_ok}"
            )
            # Fail closed — if either check failed, keep safe=False and risk_level=HIGH
            return result

        # Determine risk level
        high_risk_flags = [
            "MINT_AUTHORITY_ENABLED",
            "FREEZE_AUTHORITY_ENABLED",
            "HIGH_HOLDER_CONCENTRATION"
        ]
        medium_risk_flags = ["LP_NOT_LOCKED"]

        if any(f in result["flags"] for f in high_risk_flags):
            result["risk_level"] = "HIGH"
            result["safe"] = False
        elif any(f in result["flags"] for f in medium_risk_flags):
            result["risk_level"] = "MEDIUM"
            result["safe"] = False
        else:
            result["risk_level"] = "LOW"
            result["safe"] = True

        return result

    async def _check_rugcheck(self, token_mint: str, result: Dict) -> bool:
        """Query RugCheck.xyz. Returns True if check succeeded."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(
                    self.RUGCHECK_API.format(mint=token_mint)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        if data.get("mintAuthorityEnabled"):
                            result["mint_authority"] = True
                            result["flags"].append("MINT_AUTHORITY_ENABLED")

                        if data.get("freezeAuthorityEnabled"):
                            result["freeze_authority"] = True
                            result["flags"].append("FREEZE_AUTHORITY_ENABLED")

                        if not data.get("lpLocked"):
                            result["lp_locked"] = False
                            result["flags"].append("LP_NOT_LOCKED")
                        else:
                            result["lp_locked"] = True
                        return True
                    else:
                        logger.warning(f"RugCheck API returned {resp.status} for {token_mint}")
                        return False
        except Exception as e:
            logger.error(f"RugCheck API failed for {token_mint}: {e}")
            return False

    async def _check_solscan(self, token_mint: str, result: Dict) -> bool:
        """Query Solscan for holder concentration. Returns True if check succeeded."""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                headers = {}
                if self.solscan_api_key:
                    headers["Authorization"] = f"Bearer {self.solscan_api_key}"

                async with session.get(
                    self.SOLSCAN_API,
                    params={"tokenAddress": token_mint, "limit": 10},
                    headers=headers
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        holders = data.get("data", [])
                        total_supply = sum(h.get("amount", 0) for h in holders)
                        top10 = sum(h.get("amount", 0) for h in holders[:10])

                        if total_supply > 0:
                            result["top10_holder_pct"] = (top10 / total_supply) * 100

                        if result["top10_holder_pct"] > 50:
                            result["flags"].append("HIGH_HOLDER_CONCENTRATION")
                        return True
                    else:
                        logger.warning(f"Solscan API returned {resp.status} for {token_mint}")
                        return False
        except Exception as e:
            logger.error(f"Solscan API failed for {token_mint}: {e}")
            return False

    def quick_check(self, token_mint: str) -> bool:
        """Quick synchronous safety check (for testing)."""
        return True  # Placeholder
