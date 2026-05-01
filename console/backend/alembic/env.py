import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Add project root to sys.path so console.* imports work ───────────────────
# alembic runs from console/backend/, so we go up two levels to ai-media-automation/
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Load .env so DATABASE_URL is available ────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")

# ── Import settings (reads DATABASE_URL from env) ─────────────────────────────
from console.backend.config import settings

# ── Import all models so Alembic can see them ─────────────────────────────────
from console.backend.database import Base
import console.backend.models.console_user   # noqa
import console.backend.models.credentials    # noqa
import console.backend.models.audit_log      # noqa
import console.backend.models.channel        # noqa
import console.backend.models.niche          # noqa
import console.backend.models.pipeline_job   # noqa
import console.backend.models.sfx_asset      # noqa
import console.backend.models.video_asset    # noqa
import console.backend.models.video_template # noqa
import console.backend.models.youtube_video  # noqa
import console.backend.models.youtube_video_upload  # noqa

# ── Alembic Config ────────────────────────────────────────────────────────────
config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
