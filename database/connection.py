"""
Shared SQLAlchemy engine + session factory.
Reads DATABASE_URL from environment (pipeline.env or console/.env).
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Load pipeline.env from project root if not already loaded
_env_path = Path(__file__).parent.parent / "pipeline.env"
if _env_path.exists():
    load_dotenv(_env_path, override=False)

# Fallback to console/.env
_console_env = Path(__file__).parent.parent / "console" / ".env"
if _console_env.exists():
    load_dotenv(_console_env, override=False)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://admin:123456@localhost:5432/ai_media",
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Dependency / context manager for a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session() -> Session:
    """Return a plain session (not a generator) for use outside FastAPI."""
    return SessionLocal()
