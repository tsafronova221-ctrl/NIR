from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    bot_jwt_secret: str
    backend_api_base: str = os.getenv("BACKEND_API_BASE", "http://127.0.0.1:8000")
    frontend_base_url: str = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")
    request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "10"))
    flag: str = os.getenv("FLAG", "DUCKERZ{FAKE_FLAG}")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")

@lru_cache
def get_settings() -> Settings:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "BOT_TOKEN environment variable is required to start the bot."
        )
    secret = os.getenv("BOT_JWT_SECRET")
    if not secret:
        raise RuntimeError(
            "BOT_JWT_SECRET environment variable is required to start the bot."
        )
    return Settings(bot_token=token, bot_jwt_secret=secret)
