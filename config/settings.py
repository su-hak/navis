"""Configuration settings for the AI agent."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Anthropic API
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Model configuration
    model_name: str = os.getenv("MODEL_NAME", "claude-3-5-sonnet-20241022")
    temperature: float = float(os.getenv("TEMPERATURE", "0.7"))
    max_tokens: int = int(os.getenv("MAX_TOKENS", "4096"))

    # Agent configuration
    agent_name: str = os.getenv("AGENT_NAME", "NavisAgent")
    agent_description: str = os.getenv(
        "AGENT_DESCRIPTION",
        "A general-purpose AI agent powered by Claude"
    )

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = os.getenv("LOG_FILE", "logs/agent.log")

    # Telegram Bot
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    allowed_user_ids_str: str = os.getenv("ALLOWED_USER_IDS", "")

    @property
    def allowed_user_ids(self) -> list:
        """Parse and return allowed user IDs as a list of integers."""
        if not self.allowed_user_ids_str:
            return []
        return [
            int(uid.strip()) for uid in self.allowed_user_ids_str.split(",") if uid.strip()
        ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create logs directory if it doesn't exist
        self.logs_dir.mkdir(exist_ok=True)

    # Project paths
    project_root: Path = Path(__file__).parent.parent
    logs_dir: Path = project_root / "logs"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from environment variables


# Global settings instance
settings = Settings()
