import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://localhost/ai_media_test"
)

# Guard: refuse to run destructive fixture teardown against the production DB.
# The production DB is identified by the DATABASE_URL env var; if TEST_DATABASE_URL
# resolves to the same host+dbname, abort immediately rather than wipe data.
_PROD_DB_URL = os.environ.get("DATABASE_URL", "")
if _PROD_DB_URL and TEST_DB_URL.rstrip("/") == _PROD_DB_URL.rstrip("/"):
    raise RuntimeError(
        f"TEST_DATABASE_URL points at the production database ({TEST_DB_URL}). "
        "Set TEST_DATABASE_URL to a dedicated test database before running tests."
    )


@pytest.fixture(scope="session")
def engine():
    from console.backend.database import Base
    from console.backend.models import sfx_asset, video_template, youtube_video, video_asset, pipeline_job, channel_plan  # noqa: ensure tables registered
    eng = create_engine(TEST_DB_URL)
    Base.metadata.create_all(eng)
    yield eng
    # drop_all topo-sort can fail when Alembic-only FKs aren't declared on the
    # Base.metadata models. Fall back to DROP SCHEMA CASCADE for reliable cleanup.
    try:
        Base.metadata.drop_all(eng)
    except Exception:
        from sqlalchemy import text
        with eng.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()
