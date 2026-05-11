"""SolSniper configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API keys
    HELIUS_API_KEY: str = ""
    WALLET_PRIVATE_KEY: str = ""
    KIMI_API_KEY: str = ""
    KIMI_API_BASE: str = "https://api.moonshot.cn/v1"
    KIMI_MODEL: str = "kimi-k2"

    # Trading params
    MAX_POSITION_SIZE_USD: float = 50.0
    MIN_SNIPE_SCORE: int = 50
    PROPOSAL_EXPIRY_SECONDS: int = 180
    SLIPPAGE_BPS: int = 300

    # Helius RPC endpoint
    HELIUS_RPC_URL: str = ""

    def model_post_init(self, __context):
        if not self.HELIUS_RPC_URL:
            self.HELIUS_RPC_URL = f"https://mainnet.helius-rpc.com/?api-key={self.HELIUS_API_KEY}"


settings = Settings()
