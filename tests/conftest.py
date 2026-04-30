import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://localhost/ai_media_test"
)


@pytest.fixture(scope="session")
def engine():
    from console.backend.database import Base
    from console.backend.models import sfx_asset, video_template, youtube_video, video_asset, pipeline_job  # noqa: ensure tables registered
    eng = create_engine(TEST_DB_URL)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


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
