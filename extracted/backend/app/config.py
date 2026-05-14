from functools import lru_cache
from pathlib import Path
import os
from datetime import timedelta


class Settings:
    """Application configuration loaded from environment variables."""

    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{(BASE_DIR / 'planner.db').as_posix()}",
    )
    SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE_ME")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "4320")
    )  # 3 days by default
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "*")
    BACKEND_CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("BACKEND_CORS_ORIGINS", FRONTEND_ORIGIN).split(",")
        if origin.strip()
    ]
    FLAG_PART_PRODUCT_NAME: str = os.getenv("FLAG_PART_PRODUCT_NAME", "Часть флага")
    FLAG_PARTS_REQUIRED: int = int(os.getenv("FLAG_PARTS_REQUIRED", "5"))
    FLAG_REWARD_NAME: str = os.getenv("FLAG_REWARD_NAME", "Победа")
    FLAG_REWARD_MESSAGE: str = os.getenv(
        "FLAG_REWARD_MESSAGE",
        "Поздравляем! Вы собрали все части флага.",
    )
    BOT_JWT_SECRET: str = os.getenv("BOT_JWT_SECRET", "CHANGE_BOT_SECRET")

    @property
    def access_token_expire_timedelta(self) -> timedelta:
        return timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)


@lru_cache
def get_settings() -> Settings:
    return Settings()
