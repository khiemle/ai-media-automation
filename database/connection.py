"""
Shared SQLAlchemy engine + session factory.
Reads DATABASE_URL from environment (.env at project root).
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Load .env from project root if not already set
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=False)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://admin:123456@localhost:5432/ai_media",
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=300,
    pool_timeout=30,
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
