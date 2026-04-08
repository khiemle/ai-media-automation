import sys
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/ai_media"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # Fernet encryption key for OAuth secrets
    FERNET_KEY: str = ""

    # Path to root project (so we can import core pipeline modules)
    CORE_PIPELINE_PATH: str = ".."

    # Server
    CONSOLE_PORT: int = 8080
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # Environment
    ENV: str = "development"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Add the core pipeline root to sys.path so we can do:
        #   from rag.script_writer import generate_script
        core_path = str(Path(__file__).parent.parent.parent / self.CORE_PIPELINE_PATH)
        core_path = str(Path(core_path).resolve())
        if core_path not in sys.path:
            sys.path.insert(0, core_path)


settings = Settings()
