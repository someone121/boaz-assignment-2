"""Application configuration and directory paths for SmartClass AI."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = BASE_DIR / "uploads"
REPORTS_DIR = BASE_DIR / "reports"
STATIC_DIR = BASE_DIR / "static"


class Settings:
    """KISS runtime settings loaded from environment variables."""

    APP_NAME: str = "SmartClass AI"
    APP_VERSION: str = "1.0.0"
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'smartclass.db').as_posix()}")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecret_kiss_key")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    QUIZ_TOKEN_TTL_SECONDS: int = 300
    DEFAULT_PRESENCE_THRESHOLD: float = 0.70

    @staticmethod
    def ensure_directories() -> None:
        """Create required runtime directories if they do not exist."""
        for directory in (DATA_DIR, UPLOADS_DIR, REPORTS_DIR, STATIC_DIR):
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()
