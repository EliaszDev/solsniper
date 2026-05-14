"""Application configuration loaded from environment / .env."""
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr


class Settings(BaseSettings):
    # ── API keys (never logged) ──────────────────────────────
    HELIUS_API_KEY: SecretStr = Field(..., description="Helius API key")
    KIMI_API_KEY: SecretStr | None = Field(
        default=None, description="Moonshot (Kimi) API key"
    )

    # ── Wallet (paper or live) ───────────────────────────────
    WALLET_PRIVATE_KEY: SecretStr | None = Field(
        default=None, description="Base-58 private key (only needed for live trading)"
    )
    WALLET_PUBLIC_KEY: str | None = Field(
        default=None, description="Paper-trading wallet public key (base58)"
    )

    # ── Trading parameters ───────────────────────────────────
    MAX_POSITION_SIZE_USD: float = 100.0
    MIN_SNIPE_SCORE: float = 0.7
    PROPOSAL_EXPIRY_SECONDS: int = 300
    SLIPPAGE_BPS: int = 100

    # ── Paper trading ────────────────────────────────────────
    PAPER_TRADING: bool = Field(
        default=True,
        description="If True, skip on-chain submission and return fake signatures"
    )

    # ── Background task intervals (seconds) ──────────────────
    WHALE_POLL_INTERVAL: int = 60
    SNIPER_POLL_INTERVAL: int = 30
    POSITION_UPDATE_INTERVAL: int = 30
    PROPOSAL_EXPIRY_INTERVAL: int = 60

    # ── App secrets ──────────────────────────────────────────
    SECRET_KEY: SecretStr = Field(
        ...,
        description="JWT / session signing secret (set in .env, no default)",
    )

    # ── Derived URLs ─────────────────────────────────────────
    HELIUS_RPC_URL: str = Field(
        default="",
        description="Optional override. Auto-built if omitted.",
    )

    JUPITER_QUOTE_URL: str = Field(
        default="https://quote-api.jup.ag/v6",
        description="Jupiter Quote API base URL",
    )

    @property
    def helius_rpc_url(self) -> str:
        if self.HELIUS_RPC_URL:
            return self.HELIUS_RPC_URL
        return (
            f"https://mainnet.helius-rpc.com/?api-key="
            f"{self.HELIUS_API_KEY.get_secret_value()}"
        )

    @property
    def helius_api_base(self) -> str:
        return "https://api.helius.xyz/v0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
