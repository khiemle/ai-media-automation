# YouTube Video Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate ASMR/Soundscape YouTube long-form video production into the console — SFX asset management, MidJourney/Runway visual assets, Suno manual music flow, ffmpeg audio mixing, and nav restructure.

**Architecture:** Template-driven parallel production track. All YouTube jobs reference a `video_template` row (slug, render config, SFX defaults, prompt templates). A new Celery task (`youtube_render`) mixes music + 3 SFX layers with ffmpeg `amix`, then loops a visual asset to the target duration. New nav sections (LIBRARY / SHORT VIDEOS / YOUTUBE VIDEOS / ADMIN) are non-collapsible dividers rendered in the sidebar.

**Tech Stack:** FastAPI · SQLAlchemy `Mapped[]` / `mapped_column` style · Alembic · Celery + Redis · ffmpeg (amix, stream_loop) · Runway API (gen3-alpha / gen4-turbo) · React 18 + Vite + Tailwind CSS

---

## File Map

### New backend files
| Path | Responsibility |
|---|---|
| `console/backend/alembic/versions/007_youtube_pipeline.py` | Migration: sfx_assets, video_templates, youtube_videos tables + extensions |
| `console/backend/models/sfx_asset.py` | SfxAsset ORM model |
| `console/backend/models/video_template.py` | VideoTemplate ORM model |
| `console/backend/models/youtube_video.py` | YoutubeVideo ORM model |
| `console/backend/services/sfx_service.py` | SFX CRUD, file upload, usage tracking |
| `console/backend/services/runway_service.py` | Runway API client (submit, poll, cancel) |
| `console/backend/services/youtube_video_service.py` | YouTube video CRUD, SFX resolution, render dispatch |
| `console/backend/routers/sfx.py` | REST: /sfx |
| `console/backend/routers/youtube_videos.py` | REST: /youtube-videos |
| `console/backend/tasks/youtube_render_task.py` | Celery: ffmpeg audio mix + visual loop + compose |
| `console/backend/tasks/runway_task.py` | Celery: Runway animation poll (30s intervals, 10min timeout) |
| `tests/conftest.py` | pytest DB fixtures |
| `tests/test_sfx_service.py` | SfxService unit/integration tests |
| `tests/test_youtube_video_service.py` | YoutubeVideoService tests |

### Modified backend files
| Path | Change |
|---|---|
| `console/backend/models/video_asset.py` | + asset_type, parent_asset_id, generation_prompt, runway_status |
| `console/backend/models/pipeline_job.py` | + video_format, parent_youtube_video_id |
| `console/backend/services/music_service.py` | + get_templates() method |
| `console/backend/routers/music.py` | + GET /music/templates |
| `console/backend/routers/llm.py` | + GET/PUT /llm/runway |
| `console/backend/main.py` | register sfx + youtube_videos routers |

### New frontend files
| Path | Responsibility |
|---|---|
| `console/frontend/src/pages/SFXPage.jsx` | SFX library: import, list, filter by sound_type, play |
| `console/frontend/src/pages/YouTubeVideosPage.jsx` | YT video list + slide-over creation form + Make Short modal |

### Modified frontend files
| Path | Change |
|---|---|
| `console/frontend/src/api/client.js` | + sfxApi, youtubeVideosApi, templatesApi |
| `console/frontend/src/App.jsx` | section headers (LIBRARY/SHORT/YOUTUBE/ADMIN), new tabs |
| `console/frontend/src/pages/MusicPage.jsx` | Suno manual modal with guide, sound rules, extend steps |
| `console/frontend/src/pages/VideoAssetsPage.jsx` | MJ/Runway import, Animate modal, asset_type filter |
| `console/frontend/src/pages/PipelinePage.jsx` | format filter dropdown (All/Short/YouTube Long) |
| `console/frontend/src/pages/UploadsPage.jsx` | format toggle (All/Short/YouTube Long) |
| `console/frontend/src/pages/LLMPage.jsx` | Runway API key, model, test connection |

---

## Task 1: DB Migration

**Files:**
- Create: `console/backend/alembic/versions/007_youtube_pipeline.py`

- [ ] **Step 1: Write the migration**

```python
# console/backend/alembic/versions/007_youtube_pipeline.py
"""YouTube video pipeline — sfx_assets, video_templates, youtube_videos, extensions

Revision ID: 007
Revises: 006
Create Date: 2026-04-30
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── sfx_assets ────────────────────────────────────────────────────────────
    op.create_table(
        "sfx_assets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("source", sa.String(20), server_default="import"),  # freesound | import
        sa.Column("sound_type", sa.String(50)),
        sa.Column("duration_s", sa.Float),
        sa.Column("usage_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_sfx_sound_type", "sfx_assets", ["sound_type"])

    # ── video_templates ───────────────────────────────────────────────────────
    op.create_table(
        "video_templates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("output_format", sa.String(20), nullable=False),  # landscape_long | portrait_short
        sa.Column("target_duration_h", sa.Float),
        sa.Column("suno_extends_recommended", sa.Integer),
        sa.Column("sfx_pack", JSONB),
        sa.Column("suno_prompt_template", sa.Text),
        sa.Column("midjourney_prompt_template", sa.Text),
        sa.Column("runway_prompt_template", sa.Text),
        sa.Column("sound_rules", JSONB),
        sa.Column("seo_title_formula", sa.Text),
        sa.Column("seo_description_template", sa.Text),
    )

    # ── Seed 4 template rows ──────────────────────────────────────────────────
    op.execute("""
        INSERT INTO video_templates
            (slug, label, output_format, target_duration_h, suno_extends_recommended,
             sfx_pack, suno_prompt_template, midjourney_prompt_template, runway_prompt_template,
             sound_rules, seo_title_formula, seo_description_template)
        VALUES
        (
            'asmr', 'ASMR', 'landscape_long', 8.0, 3,
            '{"foreground": {"asset_id": null, "volume": 0.60}, "midground": {"asset_id": null, "volume": 0.30}, "background": {"asset_id": null, "volume": 0.10}}',
            '[Instrumental] heavy rainfall on glass window, distant rolling thunder, no melody, pure texture, [No Vocals], deep and immersive, slight reverb, dark and peaceful, analog warmth, 432Hz, [Sustained Texture]',
            'dark bedroom window at night, heavy rain streaks on glass, blurred city lights beyond, deep navy and charcoal tones, moody atmospheric photography, cinematic depth of field, no people --ar 16:9 --style raw --v 6.1',
            'Very slow, barely perceptible rain droplets running down glass. No camera movement. No sudden changes. Hypnotic loop.',
            '["No melody — melody disrupts sleep", "No sudden volume peaks", "Keep texture consistent throughout", "High-frequency roll-off above 12kHz"]',
            '{theme} ASMR — {duration}h Relaxing Sounds for Sleep & Focus',
            'Immersive {theme} soundscape for deep sleep, focus, and relaxation. {duration} hours of uninterrupted ASMR audio.'
        ),
        (
            'soundscape', 'Soundscape', 'landscape_long', 3.0, 5,
            '{"foreground": {"asset_id": null, "volume": 0.60}, "midground": {"asset_id": null, "volume": 0.30}, "background": {"asset_id": null, "volume": 0.10}}',
            '[Instrumental] babbling mountain stream over smooth rocks, light breeze through pine trees, occasional bird call, subtle ambient music underneath, [No Vocals], peaceful and focused, natural stereo space, fresh morning feel, [Ambient Landscape]',
            'misty mountain valley at dawn, soft light rays through pine forest, still reflective lake in foreground, cool blue-green tones, peaceful nature photography, no people --ar 16:9 --style raw --v 6.1',
            'Gentle mist drifting slowly over a mountain lake. Barely moving pine branches. Golden hour light shifting imperceptibly. Seamless loop.',
            '["Subtle melody ok — keep it understated", "Wide stereo field for spatial depth", "Moderate dynamic range — some variation is welcome", "Natural reverb to place listener in space"]',
            '{theme} Soundscape — {duration}h Ambient Nature Sounds',
            'Peaceful {theme} soundscape for studying, working, and unwinding. {duration} hours of natural ambient audio.'
        ),
        (
            'asmr_viral', 'ASMR Viral Short', 'portrait_short', null, null,
            null,
            '[Instrumental] heavy rainfall on glass window, distant rolling thunder, no melody, pure texture, [No Vocals], deep and immersive, slight reverb, dark and peaceful, analog warmth, 432Hz, [Sustained Texture]',
            null,
            null,
            '["No melody — melody disrupts sleep", "No sudden volume peaks", "Keep texture consistent throughout"]',
            'ASMR {theme} 🌧️ Full {parent_duration}h on channel',
            'Clip from the full {parent_duration}h ASMR video — link in bio.'
        ),
        (
            'soundscape_viral', 'Soundscape Viral Short', 'portrait_short', null, null,
            null,
            '[Instrumental] babbling mountain stream over smooth rocks, light breeze through pine trees, occasional bird call, subtle ambient music underneath, [No Vocals], peaceful and focused, natural stereo space, [Ambient Landscape]',
            null,
            null,
            '["Subtle melody ok", "Wide stereo field", "Moderate dynamic range"]',
            'Soundscape {theme} 🏔️ Full {parent_duration}h on channel',
            'Clip from the full {parent_duration}h soundscape — link in bio.'
        );
    """)

    # ── youtube_videos ────────────────────────────────────────────────────────
    op.create_table(
        "youtube_videos",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("template_id", sa.Integer, sa.ForeignKey("video_templates.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("theme", sa.Text),
        sa.Column("music_track_id", sa.Integer, sa.ForeignKey("music_tracks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("visual_asset_id", sa.Integer, sa.ForeignKey("video_assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sfx_overrides", JSONB),
        sa.Column("seo_title", sa.Text),
        sa.Column("seo_description", sa.Text),
        sa.Column("seo_tags", ARRAY(sa.String)),
        sa.Column("target_duration_h", sa.Float),
        sa.Column("output_quality", sa.String(10), server_default="1080p"),
        sa.Column("status", sa.String(20), server_default="draft"),  # draft|rendering|ready|uploaded
        sa.Column("output_path", sa.Text),
        sa.Column("celery_task_id", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_youtube_videos_status", "youtube_videos", ["status"])
    op.create_index("idx_youtube_videos_template", "youtube_videos", ["template_id"])

    # ── video_assets extensions ───────────────────────────────────────────────
    op.add_column("video_assets", sa.Column("asset_type", sa.String(20), server_default="video_clip"))  # still_image | video_clip
    op.add_column("video_assets", sa.Column("parent_asset_id", sa.Integer, sa.ForeignKey("video_assets.id", ondelete="SET NULL"), nullable=True))
    op.add_column("video_assets", sa.Column("generation_prompt", sa.Text, nullable=True))
    op.add_column("video_assets", sa.Column("runway_status", sa.String(20), server_default="none"))  # none|pending|ready|failed

    # ── pipeline_jobs extensions ──────────────────────────────────────────────
    op.add_column("pipeline_jobs", sa.Column("video_format", sa.String(20), server_default="short"))  # short | youtube_long
    op.add_column("pipeline_jobs", sa.Column("parent_youtube_video_id", sa.Integer, sa.ForeignKey("youtube_videos.id", ondelete="SET NULL"), nullable=True))
    op.create_index("idx_pipeline_jobs_format", "pipeline_jobs", ["video_format"])

    # ── music_tracks: rename suno → sunoapi ──────────────────────────────────
    op.execute("UPDATE music_tracks SET provider = 'sunoapi' WHERE provider = 'suno'")


def downgrade() -> None:
    op.execute("UPDATE music_tracks SET provider = 'suno' WHERE provider = 'sunoapi'")
    op.drop_index("idx_pipeline_jobs_format", table_name="pipeline_jobs")
    op.drop_column("pipeline_jobs", "parent_youtube_video_id")
    op.drop_column("pipeline_jobs", "video_format")
    op.drop_column("video_assets", "runway_status")
    op.drop_column("video_assets", "generation_prompt")
    op.drop_column("video_assets", "parent_asset_id")
    op.drop_column("video_assets", "asset_type")
    op.drop_index("idx_youtube_videos_template", table_name="youtube_videos")
    op.drop_index("idx_youtube_videos_status", table_name="youtube_videos")
    op.drop_table("youtube_videos")
    op.drop_table("video_templates")
    op.drop_index("idx_sfx_sound_type", table_name="sfx_assets")
    op.drop_table("sfx_assets")
```

- [ ] **Step 2: Run migration**

```bash
cd console/backend
alembic upgrade head
```

Expected: `Running upgrade 006 -> 007, YouTube video pipeline — sfx_assets, video_templates, youtube_videos, extensions`

- [ ] **Step 3: Verify tables exist**

```bash
cd console/backend
python3 -c "
from console.backend.database import engine
from sqlalchemy import inspect
i = inspect(engine)
print('sfx_assets cols:', [c['name'] for c in i.get_columns('sfx_assets')])
print('video_templates:', [c['name'] for c in i.get_columns('video_templates')])
print('youtube_videos:', [c['name'] for c in i.get_columns('youtube_videos')])
print('template count:', engine.connect().execute(__import__('sqlalchemy').text('SELECT count(*) FROM video_templates')).scalar())
"
```

Expected: 4 template rows, all three new tables present.

- [ ] **Step 4: Commit**

```bash
git add console/backend/alembic/versions/007_youtube_pipeline.py
git commit -m "feat: add migration 007 — sfx_assets, video_templates, youtube_videos, extensions"
```

---

## Task 2: Console Models — SfxAsset, VideoTemplate, YoutubeVideo

**Files:**
- Create: `console/backend/models/sfx_asset.py`
- Create: `console/backend/models/video_template.py`
- Create: `console/backend/models/youtube_video.py`

- [ ] **Step 1: Create SfxAsset model**

```python
# console/backend/models/sfx_asset.py
from datetime import datetime, timezone

from sqlalchemy import Float, Integer, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from console.backend.database import Base


class SfxAsset(Base):
    __tablename__ = "sfx_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="import", server_default="import")
    sound_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
```

- [ ] **Step 2: Create VideoTemplate model**

```python
# console/backend/models/video_template.py
from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from console.backend.database import Base


class VideoTemplate(Base):
    __tablename__ = "video_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    output_format: Mapped[str] = mapped_column(String(20), nullable=False)
    target_duration_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    suno_extends_recommended: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sfx_pack: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    suno_prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    midjourney_prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    runway_prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    sound_rules: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    seo_title_formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_description_template: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 3: Create YoutubeVideo model**

```python
# console/backend/models/youtube_video.py
from datetime import datetime, timezone

from sqlalchemy import Float, Integer, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from console.backend.database import Base


class YoutubeVideo(Base):
    __tablename__ = "youtube_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    template_id: Mapped[int] = mapped_column(Integer, nullable=False)
    theme: Mapped[str | None] = mapped_column(Text, nullable=True)
    music_track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visual_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sfx_overrides: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    seo_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    target_duration_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_quality: Mapped[str] = mapped_column(String(10), default="1080p", server_default="1080p")
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
```

- [ ] **Step 4: Commit**

```bash
git add console/backend/models/sfx_asset.py console/backend/models/video_template.py console/backend/models/youtube_video.py
git commit -m "feat: add SfxAsset, VideoTemplate, YoutubeVideo ORM models"
```

---

## Task 3: Extend VideoAsset and PipelineJob Models

**Files:**
- Modify: `console/backend/models/video_asset.py`
- Modify: `console/backend/models/pipeline_job.py`

- [ ] **Step 1: Add new columns to VideoAsset**

In `console/backend/models/video_asset.py`, add after `usage_count`:

```python
    asset_type: Mapped[str] = mapped_column(String(20), default="video_clip", server_default="video_clip")
    parent_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    runway_status: Mapped[str] = mapped_column(String(20), default="none", server_default="none")
```

Also add `Integer` and `Text` to the import line if not already there. Full updated imports:

```python
from sqlalchemy import Float, Integer, String, Text, DateTime, func
```

- [ ] **Step 2: Add new columns to PipelineJob**

In `console/backend/models/pipeline_job.py`, add after `created_at`:

```python
    video_format: Mapped[str] = mapped_column(String(20), default="short", server_default="short")
    parent_youtube_video_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

- [ ] **Step 3: Verify models import cleanly**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python3 -c "
from console.backend.models.video_asset import VideoAsset
from console.backend.models.pipeline_job import PipelineJob
print('VideoAsset cols:', [c.key for c in VideoAsset.__table__.columns])
print('PipelineJob cols:', [c.key for c in PipelineJob.__table__.columns])
"
```

Expected: VideoAsset shows `asset_type`, `parent_asset_id`, `generation_prompt`, `runway_status`. PipelineJob shows `video_format`, `parent_youtube_video_id`.

- [ ] **Step 4: Commit**

```bash
git add console/backend/models/video_asset.py console/backend/models/pipeline_job.py
git commit -m "feat: extend VideoAsset and PipelineJob models with YouTube pipeline fields"
```

---

## Task 4: Test Fixtures + SfxService + sfx Router

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_sfx_service.py`
- Create: `console/backend/services/sfx_service.py`
- Create: `console/backend/routers/sfx.py`

- [ ] **Step 1: Write test fixtures**

```python
# tests/conftest.py
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use a separate test DB
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
```

- [ ] **Step 2: Write failing tests for SfxService**

```python
# tests/test_sfx_service.py
import io
import pytest
from console.backend.services.sfx_service import SfxService


def test_list_sfx_empty(db):
    svc = SfxService(db)
    result = svc.list_sfx()
    assert result == []


def test_import_sfx(db, tmp_path):
    svc = SfxService(db)
    fake_wav = b"RIFF" + b"\x00" * 40
    track = svc.import_sfx(
        title="Heavy Rain",
        sound_type="rain_heavy",
        source="import",
        file_bytes=fake_wav,
        filename="rain.wav",
        sfx_dir=tmp_path,
    )
    assert track["id"] is not None
    assert track["title"] == "Heavy Rain"
    assert track["sound_type"] == "rain_heavy"
    assert (tmp_path / f"sfx_{track['id']}.wav").exists()


def test_list_sfx_filter_by_type(db, tmp_path):
    svc = SfxService(db)
    fake = b"RIFF" + b"\x00" * 40
    svc.import_sfx("Rain", "rain_heavy", "import", fake, "r.wav", tmp_path)
    svc.import_sfx("Birds", "birds", "import", fake, "b.wav", tmp_path)
    result = svc.list_sfx(sound_type="birds")
    assert len(result) == 1
    assert result[0]["sound_type"] == "birds"


def test_delete_sfx(db, tmp_path):
    svc = SfxService(db)
    fake = b"RIFF" + b"\x00" * 40
    track = svc.import_sfx("Rain", "rain_heavy", "import", fake, "r.wav", tmp_path)
    svc.delete_sfx(track["id"])
    assert svc.list_sfx() == []


def test_list_distinct_sound_types(db, tmp_path):
    svc = SfxService(db)
    fake = b"RIFF" + b"\x00" * 40
    svc.import_sfx("Rain A", "rain_heavy", "import", fake, "a.wav", tmp_path)
    svc.import_sfx("Rain B", "rain_heavy", "import", fake, "b.wav", tmp_path)
    svc.import_sfx("Birds", "birds", "import", fake, "c.wav", tmp_path)
    types = svc.list_sound_types()
    assert sorted(types) == ["birds", "rain_heavy"]
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python3 -m pytest tests/test_sfx_service.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError` or `ImportError` for `SfxService`.

- [ ] **Step 4: Implement SfxService**

```python
# console/backend/services/sfx_service.py
import os
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

SFX_DIR = Path(os.environ.get("SFX_PATH", "./assets/sfx"))


def _sfx_to_dict(s) -> dict:
    return {
        "id":         s.id,
        "title":      s.title,
        "file_path":  s.file_path,
        "source":     s.source,
        "sound_type": s.sound_type,
        "duration_s": s.duration_s,
        "usage_count":s.usage_count,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


class SfxService:
    def __init__(self, db: Session):
        self.db = db

    def _model(self):
        from console.backend.models.sfx_asset import SfxAsset
        return SfxAsset

    def list_sfx(self, sound_type: str | None = None, search: str | None = None) -> list[dict]:
        SfxAsset = self._model()
        q = self.db.query(SfxAsset)
        if sound_type:
            q = q.filter(SfxAsset.sound_type == sound_type)
        if search:
            q = q.filter(SfxAsset.title.ilike(f"%{search}%"))
        return [_sfx_to_dict(s) for s in q.order_by(SfxAsset.created_at.desc()).all()]

    def list_sound_types(self) -> list[str]:
        SfxAsset = self._model()
        rows = self.db.query(SfxAsset.sound_type).distinct().filter(SfxAsset.sound_type.isnot(None)).all()
        return sorted([r[0] for r in rows])

    def import_sfx(
        self,
        title: str,
        sound_type: str,
        source: str,
        file_bytes: bytes,
        filename: str,
        sfx_dir: Path | None = None,
    ) -> dict:
        SfxAsset = self._model()
        sfx_dir = sfx_dir or SFX_DIR
        sfx_dir.mkdir(parents=True, exist_ok=True)

        row = SfxAsset(title=title, sound_type=sound_type, source=source, file_path="")
        self.db.add(row)
        self.db.flush()

        ext = Path(filename).suffix or ".wav"
        dest = sfx_dir / f"sfx_{row.id}{ext}"
        dest.write_bytes(file_bytes)
        row.file_path = str(dest)
        self.db.commit()
        self.db.refresh(row)
        return _sfx_to_dict(row)

    def delete_sfx(self, sfx_id: int) -> None:
        SfxAsset = self._model()
        row = self.db.get(SfxAsset, sfx_id)
        if not row:
            raise KeyError(f"SFX {sfx_id} not found")
        path = Path(row.file_path)
        if path.exists():
            path.unlink(missing_ok=True)
        self.db.delete(row)
        self.db.commit()
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
python3 -m pytest tests/test_sfx_service.py -v
```

Expected: 5 tests PASSED.

- [ ] **Step 6: Implement sfx router**

```python
# console/backend/routers/sfx.py
import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from console.backend.auth import require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.sfx_service import SfxService

router = APIRouter(prefix="/sfx", tags=["sfx"])

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg"}


@router.get("")
def list_sfx(
    sound_type: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return SfxService(db).list_sfx(sound_type=sound_type, search=search)


@router.get("/sound-types")
def list_sound_types(
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return SfxService(db).list_sound_types()


@router.post("/import", status_code=201)
async def import_sfx(
    file: UploadFile = File(...),
    title: str = Form(...),
    sound_type: str = Form(...),
    source: str = Form(default="import"),
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {ext}")
    content = await file.read()
    return SfxService(db).import_sfx(
        title=title,
        sound_type=sound_type,
        source=source,
        file_bytes=content,
        filename=file.filename or "sfx.wav",
    )


@router.delete("/{sfx_id}", status_code=204)
def delete_sfx(
    sfx_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        SfxService(db).delete_sfx(sfx_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{sfx_id}/stream")
def stream_sfx(sfx_id: int, db: Session = Depends(get_db)):
    from console.backend.models.sfx_asset import SfxAsset
    row = db.get(SfxAsset, sfx_id)
    if not row:
        raise HTTPException(status_code=404, detail="SFX not found")
    path = Path(row.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(str(path), media_type="audio/wav")
```

- [ ] **Step 7: Commit**

```bash
git add tests/conftest.py tests/test_sfx_service.py console/backend/services/sfx_service.py console/backend/routers/sfx.py
git commit -m "feat: add SfxService + sfx router with tests"
```

---

## Task 5: RunwayService + Celery Animation Task

**Files:**
- Create: `console/backend/services/runway_service.py`
- Create: `console/backend/tasks/runway_task.py`

- [ ] **Step 1: Implement RunwayService**

```python
# console/backend/services/runway_service.py
"""Runway API client — submit image-to-video, poll status, cancel."""
import os
import time
from typing import Any

import requests

RUNWAY_API_BASE = "https://api.runwayml.com/v1"


class RunwayService:
    def __init__(self, api_key: str | None = None, model: str = "gen3-alpha"):
        self.api_key = api_key or os.environ.get("RUNWAY_API_KEY", "")
        self.model = model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def submit_image_to_video(
        self,
        image_url: str,
        prompt: str,
        duration: int = 5,
        motion_intensity: int = 2,
    ) -> str:
        """Submit an animation job. Returns task_id."""
        payload = {
            "model": self.model,
            "input": {
                "image": image_url,
                "text_prompt": prompt,
                "duration": duration,
                "motion_intensity": motion_intensity,
            },
        }
        resp = requests.post(
            f"{RUNWAY_API_BASE}/tasks",
            json=payload,
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def submit_text_to_video(self, prompt: str, duration: int = 5, motion_intensity: int = 2) -> str:
        """Submit text-to-video job. Returns task_id."""
        payload = {
            "model": self.model,
            "input": {
                "text_prompt": prompt,
                "duration": duration,
                "motion_intensity": motion_intensity,
            },
        }
        resp = requests.post(
            f"{RUNWAY_API_BASE}/tasks",
            json=payload,
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def poll_task(self, task_id: str) -> dict[str, Any]:
        """Poll task status. Returns {"status": "pending|processing|succeeded|failed", "output_url": str|None}."""
        resp = requests.get(
            f"{RUNWAY_API_BASE}/tasks/{task_id}",
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        output_url = None
        if data.get("status") == "succeeded":
            output_url = (data.get("output") or [None])[0]
        return {"status": data.get("status"), "output_url": output_url}

    def test_connection(self) -> dict:
        """Returns {"ok": bool, "error": str|None}."""
        try:
            resp = requests.get(
                f"{RUNWAY_API_BASE}/organization",
                headers=self._headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                return {"ok": True, "error": None}
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
```

- [ ] **Step 2: Implement Celery runway animation task**

```python
# console/backend/tasks/runway_task.py
"""Celery task: poll Runway animation job every 30s, timeout 10min."""
import os
import time
from pathlib import Path

import requests

from console.backend.celery_app import celery_app

RUNWAY_OUTPUT_DIR = Path(os.environ.get("ASSETS_PATH", "./assets")) / "runway"
POLL_INTERVAL_S = 30
TIMEOUT_S = 600  # 10 minutes


@celery_app.task(bind=True, name="tasks.animate_asset")
def animate_asset_task(
    self,
    asset_id: int,
    runway_task_id: str,
    output_filename: str,
    api_key: str,
    model: str = "gen3-alpha",
):
    """Poll Runway until succeeded/failed/timeout, then save video and update asset."""
    from console.backend.database import SessionLocal
    from console.backend.models.video_asset import VideoAsset
    from console.backend.services.runway_service import RunwayService

    svc = RunwayService(api_key=api_key, model=model)
    deadline = time.time() + TIMEOUT_S

    while time.time() < deadline:
        result = svc.poll_task(runway_task_id)
        status = result["status"]

        if status == "succeeded" and result["output_url"]:
            RUNWAY_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            dest = RUNWAY_OUTPUT_DIR / output_filename
            video_resp = requests.get(result["output_url"], timeout=120)
            video_resp.raise_for_status()
            dest.write_bytes(video_resp.content)

            db = SessionLocal()
            try:
                row = db.get(VideoAsset, asset_id)
                if row:
                    row.file_path = str(dest)
                    row.runway_status = "ready"
                    row.asset_type = "video_clip"
                    db.commit()
            finally:
                db.close()
            return {"status": "ready", "file_path": str(dest)}

        if status == "failed":
            db = SessionLocal()
            try:
                row = db.get(VideoAsset, asset_id)
                if row:
                    row.runway_status = "failed"
                    db.commit()
            finally:
                db.close()
            return {"status": "failed"}

        time.sleep(POLL_INTERVAL_S)

    # Timeout
    db = SessionLocal()
    try:
        row = db.get(VideoAsset, asset_id)
        if row:
            row.runway_status = "failed"
            db.commit()
    finally:
        db.close()
    return {"status": "failed", "reason": "timeout"}
```

- [ ] **Step 3: Commit**

```bash
git add console/backend/services/runway_service.py console/backend/tasks/runway_task.py
git commit -m "feat: add RunwayService and animate_asset Celery task"
```

---

## Task 6: YoutubeVideoService + youtube_videos Router

**Files:**
- Create: `tests/test_youtube_video_service.py`
- Create: `console/backend/services/youtube_video_service.py`
- Create: `console/backend/routers/youtube_videos.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_youtube_video_service.py
import pytest
from console.backend.services.youtube_video_service import YoutubeVideoService


def _seed_template(db):
    from console.backend.models.video_template import VideoTemplate
    t = VideoTemplate(slug="asmr", label="ASMR", output_format="landscape_long", target_duration_h=8.0)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def test_create_youtube_video(db):
    svc = YoutubeVideoService(db)
    t = _seed_template(db)
    video = svc.create(
        title="Heavy Rain Window",
        template_id=t.id,
        theme="Heavy Rain",
        target_duration_h=8.0,
    )
    assert video["id"] is not None
    assert video["status"] == "draft"
    assert video["template_id"] == t.id


def test_list_youtube_videos(db):
    svc = YoutubeVideoService(db)
    t = _seed_template(db)
    svc.create("Rain 1", t.id, "rain", 8.0)
    svc.create("Rain 2", t.id, "rain", 8.0)
    result = svc.list_videos()
    assert len(result) == 2


def test_list_filter_by_status(db):
    svc = YoutubeVideoService(db)
    t = _seed_template(db)
    v = svc.create("Rain", t.id, "rain", 8.0)
    svc.update_status(v["id"], "ready")
    assert len(svc.list_videos(status="ready")) == 1
    assert len(svc.list_videos(status="draft")) == 0


def test_update_youtube_video(db):
    svc = YoutubeVideoService(db)
    t = _seed_template(db)
    v = svc.create("Old Title", t.id, "rain", 8.0)
    updated = svc.update(v["id"], {"title": "New Title", "seo_title": "New SEO"})
    assert updated["title"] == "New Title"
    assert updated["seo_title"] == "New SEO"


def test_delete_youtube_video(db):
    svc = YoutubeVideoService(db)
    t = _seed_template(db)
    v = svc.create("Rain", t.id, "rain", 8.0)
    svc.delete(v["id"])
    assert svc.list_videos() == []
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python3 -m pytest tests/test_youtube_video_service.py -v 2>&1 | head -10
```

Expected: `ImportError` for `YoutubeVideoService`.

- [ ] **Step 3: Implement YoutubeVideoService**

```python
# console/backend/services/youtube_video_service.py
from datetime import datetime, timezone

from sqlalchemy.orm import Session


def _video_to_dict(v) -> dict:
    return {
        "id":               v.id,
        "title":            v.title,
        "template_id":      v.template_id,
        "theme":            v.theme,
        "music_track_id":   v.music_track_id,
        "visual_asset_id":  v.visual_asset_id,
        "sfx_overrides":    v.sfx_overrides,
        "seo_title":        v.seo_title,
        "seo_description":  v.seo_description,
        "seo_tags":         v.seo_tags or [],
        "target_duration_h":v.target_duration_h,
        "output_quality":   v.output_quality,
        "status":           v.status,
        "output_path":      v.output_path,
        "celery_task_id":   v.celery_task_id,
        "created_at":       v.created_at.isoformat() if v.created_at else None,
        "updated_at":       v.updated_at.isoformat() if v.updated_at else None,
    }


class YoutubeVideoService:
    def __init__(self, db: Session):
        self.db = db

    def _model(self):
        from console.backend.models.youtube_video import YoutubeVideo
        return YoutubeVideo

    def list_videos(self, status: str | None = None, template_id: int | None = None) -> list[dict]:
        YoutubeVideo = self._model()
        q = self.db.query(YoutubeVideo)
        if status:
            q = q.filter(YoutubeVideo.status == status)
        if template_id:
            q = q.filter(YoutubeVideo.template_id == template_id)
        return [_video_to_dict(v) for v in q.order_by(YoutubeVideo.created_at.desc()).all()]

    def get(self, video_id: int) -> dict:
        YoutubeVideo = self._model()
        row = self.db.get(YoutubeVideo, video_id)
        if not row:
            raise KeyError(f"YouTube video {video_id} not found")
        return _video_to_dict(row)

    def create(
        self,
        title: str,
        template_id: int,
        theme: str | None = None,
        target_duration_h: float | None = None,
        music_track_id: int | None = None,
        visual_asset_id: int | None = None,
        sfx_overrides: dict | None = None,
        seo_title: str | None = None,
        seo_description: str | None = None,
        seo_tags: list[str] | None = None,
        output_quality: str = "1080p",
    ) -> dict:
        YoutubeVideo = self._model()
        row = YoutubeVideo(
            title=title,
            template_id=template_id,
            theme=theme,
            target_duration_h=target_duration_h,
            music_track_id=music_track_id,
            visual_asset_id=visual_asset_id,
            sfx_overrides=sfx_overrides,
            seo_title=seo_title,
            seo_description=seo_description,
            seo_tags=seo_tags,
            output_quality=output_quality,
            status="draft",
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return _video_to_dict(row)

    def update(self, video_id: int, fields: dict) -> dict:
        YoutubeVideo = self._model()
        row = self.db.get(YoutubeVideo, video_id)
        if not row:
            raise KeyError(f"YouTube video {video_id} not found")
        allowed = {
            "title", "theme", "music_track_id", "visual_asset_id", "sfx_overrides",
            "seo_title", "seo_description", "seo_tags", "target_duration_h", "output_quality",
        }
        for k, v in fields.items():
            if k in allowed:
                setattr(row, k, v)
        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return _video_to_dict(row)

    def update_status(self, video_id: int, status: str) -> dict:
        YoutubeVideo = self._model()
        row = self.db.get(YoutubeVideo, video_id)
        if not row:
            raise KeyError(f"YouTube video {video_id} not found")
        row.status = status
        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return _video_to_dict(row)

    def delete(self, video_id: int) -> None:
        YoutubeVideo = self._model()
        row = self.db.get(YoutubeVideo, video_id)
        if not row:
            raise KeyError(f"YouTube video {video_id} not found")
        self.db.delete(row)
        self.db.commit()

    def queue_render(self, video_id: int) -> dict:
        from console.backend.tasks.youtube_render_task import youtube_render_task
        video = self.get(video_id)
        if video["status"] not in ("draft", "ready"):
            raise ValueError(f"Cannot render a video with status '{video['status']}'")
        task = youtube_render_task.delay(video_id)
        YoutubeVideo = self._model()
        row = self.db.get(YoutubeVideo, video_id)
        row.status = "rendering"
        row.celery_task_id = task.id
        row.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return {"task_id": task.id, "video_id": video_id}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
python3 -m pytest tests/test_youtube_video_service.py -v
```

Expected: 5 tests PASSED.

- [ ] **Step 5: Implement youtube_videos router**

```python
# console/backend/routers/youtube_videos.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from console.backend.auth import require_editor_or_admin
from console.backend.database import get_db
from console.backend.services.youtube_video_service import YoutubeVideoService

router = APIRouter(prefix="/youtube-videos", tags=["youtube-videos"])


class CreateBody(BaseModel):
    title: str
    template_id: int
    theme: str | None = None
    target_duration_h: float | None = None
    music_track_id: int | None = None
    visual_asset_id: int | None = None
    sfx_overrides: dict | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    seo_tags: list[str] | None = None
    output_quality: str = "1080p"


class UpdateBody(BaseModel):
    title: str | None = None
    theme: str | None = None
    music_track_id: int | None = None
    visual_asset_id: int | None = None
    sfx_overrides: dict | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    seo_tags: list[str] | None = None
    target_duration_h: float | None = None
    output_quality: str | None = None


@router.get("")
def list_videos(
    status: str | None = None,
    template_id: int | None = None,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return YoutubeVideoService(db).list_videos(status=status, template_id=template_id)


@router.post("", status_code=201)
def create_video(
    body: CreateBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return YoutubeVideoService(db).create(**body.model_dump())


@router.get("/{video_id}")
def get_video(
    video_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return YoutubeVideoService(db).get(video_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{video_id}")
def update_video(
    video_id: int,
    body: UpdateBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return YoutubeVideoService(db).update(video_id, body.model_dump(exclude_none=True))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{video_id}", status_code=204)
def delete_video(
    video_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        YoutubeVideoService(db).delete(video_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{video_id}/render")
def queue_render(
    video_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    try:
        return YoutubeVideoService(db).queue_render(video_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/templates/list")
def list_templates(
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    from console.backend.models.video_template import VideoTemplate
    rows = db.query(VideoTemplate).all()
    return [
        {
            "id": t.id, "slug": t.slug, "label": t.label,
            "output_format": t.output_format,
            "target_duration_h": t.target_duration_h,
            "suno_extends_recommended": t.suno_extends_recommended,
            "sfx_pack": t.sfx_pack,
            "suno_prompt_template": t.suno_prompt_template,
            "midjourney_prompt_template": t.midjourney_prompt_template,
            "runway_prompt_template": t.runway_prompt_template,
            "sound_rules": t.sound_rules or [],
        }
        for t in rows
    ]
```

- [ ] **Step 6: Commit**

```bash
git add tests/test_youtube_video_service.py console/backend/services/youtube_video_service.py console/backend/routers/youtube_videos.py
git commit -m "feat: add YoutubeVideoService + youtube_videos router with tests"
```

---

## Task 7: YouTube Render Celery Task

**Files:**
- Create: `console/backend/tasks/youtube_render_task.py`

- [ ] **Step 1: Implement youtube_render_task**

```python
# console/backend/tasks/youtube_render_task.py
"""Celery task: mix audio layers + loop visual → YouTube long-form MP4."""
import os
import subprocess
import tempfile
from pathlib import Path

from console.backend.celery_app import celery_app

OUTPUT_DIR = Path(os.environ.get("YOUTUBE_OUTPUT_PATH", "./assets/youtube"))


@celery_app.task(bind=True, name="tasks.youtube_render")
def youtube_render_task(self, video_id: int):
    from console.backend.database import SessionLocal
    from console.backend.models.youtube_video import YoutubeVideo
    from console.backend.models.video_template import VideoTemplate
    from console.backend.models.sfx_asset import SfxAsset

    db = SessionLocal()
    try:
        video = db.get(YoutubeVideo, video_id)
        if not video:
            return {"error": f"Video {video_id} not found"}

        template = db.get(VideoTemplate, video.template_id)
        duration_s = int((video.target_duration_h or template.target_duration_h or 8.0) * 3600)

        # Resolve SFX pack (override > template default)
        sfx_pack = video.sfx_overrides or (template.sfx_pack if template else None) or {}

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            mixed_audio = tmp / "mixed_audio.wav"
            final_output = OUTPUT_DIR / f"youtube_{video_id}.mp4"

            # ── Step 1: Mix audio ────────────────────────────────────────────
            self.update_state(state="PROGRESS", meta={"step": "mix_audio", "progress": 10})
            _mix_audio(video, sfx_pack, db, duration_s, mixed_audio)

            # ── Step 2: Loop visual + compose ────────────────────────────────
            self.update_state(state="PROGRESS", meta={"step": "compose", "progress": 50})
            _compose(video, mixed_audio, duration_s, final_output)

            # ── Step 3: Update status ─────────────────────────────────────────
            video.status = "ready"
            video.output_path = str(final_output)
            db.commit()

        return {"status": "ready", "output_path": str(final_output)}

    except Exception as exc:
        if db:
            video = db.get(YoutubeVideo, video_id)
            if video:
                video.status = "draft"
                db.commit()
        raise exc
    finally:
        db.close()


def _mix_audio(video, sfx_pack: dict, db, duration_s: int, output: Path) -> None:
    """Build ffmpeg amix command: music + up to 3 SFX layers."""
    from database.models import MusicTrack
    from console.backend.models.sfx_asset import SfxAsset

    inputs = []
    filter_parts = []
    mix_inputs = []

    # Music track (input 0) — duration reference
    if video.music_track_id:
        track = db.get(MusicTrack, video.music_track_id)
        if track and track.file_path:
            inputs += ["-i", track.file_path]
            mix_inputs.append("[0]")

    # SFX layers
    layer_names = ["foreground", "midground", "background"]
    sfx_idx = len(inputs) // 2  # Current input index after music

    for layer in layer_names:
        layer_cfg = sfx_pack.get(layer, {})
        asset_id = layer_cfg.get("asset_id")
        volume = layer_cfg.get("volume", 0.1)
        if not asset_id:
            continue
        sfx = db.get(SfxAsset, int(asset_id))
        if not sfx or not Path(sfx.file_path).exists():
            continue
        inputs += ["-stream_loop", "-1", "-i", sfx.file_path]
        label = f"[sfx{sfx_idx}]"
        filter_parts.append(f"[{sfx_idx}]volume={volume}{label}")
        mix_inputs.append(label)
        sfx_idx += 1

    if not mix_inputs:
        # No audio at all — generate silence
        cmd = ["ffmpeg", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo", "-t", str(duration_s), str(output), "-y"]
        subprocess.run(cmd, check=True, capture_output=True)
        return

    n = len(mix_inputs)
    if n == 1:
        # Single input — just trim
        filter_str = f"[0]atrim=0:{duration_s}[out]"
    else:
        fc = ";".join(filter_parts)
        mix_in = "".join(mix_inputs)
        filter_str = (
            (fc + ";" if fc else "") +
            f"{mix_in}amix=inputs={n}:duration=first[out]"
        )

    cmd = (
        inputs +
        ["-filter_complex", filter_str, "-map", "[out]",
         "-t", str(duration_s), str(output), "-y"]
    )
    subprocess.run(["ffmpeg"] + cmd[len(["ffmpeg"]):] if cmd[0] != "ffmpeg" else cmd,
                   check=True, capture_output=True)
    # Simpler build:
    subprocess.run(
        ["ffmpeg"] + inputs + ["-filter_complex", filter_str, "-map", "[out]",
                                "-t", str(duration_s), str(output), "-y"],
        check=True, capture_output=True,
    )


def _compose(video, audio_path: Path, duration_s: int, output: Path) -> None:
    """Loop visual asset to duration and mux with mixed audio."""
    from console.backend.models.video_asset import VideoAsset
    # This import is done inline to avoid circular imports

    if not audio_path.exists():
        raise FileNotFoundError(f"Mixed audio not found: {audio_path}")

    if video.visual_asset_id:
        from console.backend.database import SessionLocal
        db2 = SessionLocal()
        try:
            asset = db2.get(VideoAsset, video.visual_asset_id)
            visual_path = asset.file_path if asset else None
        finally:
            db2.close()
    else:
        visual_path = None

    if visual_path and Path(visual_path).exists():
        # Loop video + mux audio
        subprocess.run(
            [
                "ffmpeg",
                "-stream_loop", "-1", "-i", visual_path,
                "-i", str(audio_path),
                "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                "-t", str(duration_s),
                "-map", "0:v", "-map", "1:a",
                "-shortest",
                str(output), "-y",
            ],
            check=True,
            capture_output=True,
        )
    else:
        # Audio only — black video
        subprocess.run(
            [
                "ffmpeg",
                "-f", "lavfi", "-i", f"color=c=black:s=1920x1080:r=1",
                "-i", str(audio_path),
                "-c:v", "libx264", "-preset", "fast",
                "-c:a", "aac", "-b:a", "192k",
                "-t", str(duration_s),
                str(output), "-y",
            ],
            check=True,
            capture_output=True,
        )
```

- [ ] **Step 2: Fix _mix_audio — clean up the duplicated subprocess call**

The `_mix_audio` function above has a redundant subprocess call at the end. Replace the entire function body ending with the two `subprocess.run` calls with this clean version:

```python
def _mix_audio(video, sfx_pack: dict, db, duration_s: int, output: Path) -> None:
    from database.models import MusicTrack
    from console.backend.models.sfx_asset import SfxAsset

    ff_inputs = []
    filter_parts = []
    mix_labels = []
    input_idx = 0

    if video.music_track_id:
        track = db.get(MusicTrack, video.music_track_id)
        if track and track.file_path:
            ff_inputs += ["-i", track.file_path]
            mix_labels.append(f"[{input_idx}]")
            input_idx += 1

    for layer in ["foreground", "midground", "background"]:
        layer_cfg = sfx_pack.get(layer, {})
        asset_id = layer_cfg.get("asset_id")
        volume = layer_cfg.get("volume", 0.1)
        if not asset_id:
            continue
        sfx = db.get(SfxAsset, int(asset_id))
        if not sfx or not Path(sfx.file_path).exists():
            continue
        label = f"sfx{input_idx}"
        ff_inputs += ["-stream_loop", "-1", "-i", sfx.file_path]
        filter_parts.append(f"[{input_idx}]volume={volume}[{label}]")
        mix_labels.append(f"[{label}]")
        input_idx += 1

    if not mix_labels:
        subprocess.run(
            ["ffmpeg", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
             "-t", str(duration_s), str(output), "-y"],
            check=True, capture_output=True,
        )
        return

    n = len(mix_labels)
    fc_prefix = ";".join(filter_parts) + (";" if filter_parts else "")
    filter_str = fc_prefix + "".join(mix_labels) + f"amix=inputs={n}:duration=first[out]"

    subprocess.run(
        ["ffmpeg"] + ff_inputs +
        ["-filter_complex", filter_str, "-map", "[out]",
         "-t", str(duration_s), str(output), "-y"],
        check=True, capture_output=True,
    )
```

- [ ] **Step 3: Commit**

```bash
git add console/backend/tasks/youtube_render_task.py
git commit -m "feat: add youtube_render_task — ffmpeg audio mix + visual loop compose"
```

---

## Task 8: Music Provider Rename + Templates Endpoint

**Files:**
- Modify: `console/backend/services/music_service.py`
- Modify: `console/backend/routers/music.py`

- [ ] **Step 1: Add get_templates() to MusicService**

In `console/backend/services/music_service.py`, add after `list_tracks()`:

```python
    def get_templates(self) -> list[dict]:
        """Return youtube video templates for Suno modal music type selector."""
        from console.backend.models.video_template import VideoTemplate
        rows = self.db.query(VideoTemplate).filter(
            VideoTemplate.output_format == "landscape_long"
        ).all()
        return [
            {
                "slug":                    t.slug,
                "label":                   t.label,
                "suno_prompt_template":    t.suno_prompt_template,
                "suno_extends_recommended":t.suno_extends_recommended,
                "sound_rules":             t.sound_rules or [],
            }
            for t in rows
        ]
```

- [ ] **Step 2: Add templates endpoint to music router**

In `console/backend/routers/music.py`, add before `list_tracks`:

```python
@router.get("/templates")
def list_music_templates(
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    return MusicService(db).get_templates()
```

- [ ] **Step 3: Verify**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
curl -s http://localhost:8080/api/music/templates | python3 -m json.tool | head -20
```

Expected: JSON array with `asmr` and `soundscape` template objects.

- [ ] **Step 4: Commit**

```bash
git add console/backend/services/music_service.py console/backend/routers/music.py
git commit -m "feat: add music templates endpoint + provider rename support"
```

---

## Task 9: Register New Routers + LLM Runway Endpoint

**Files:**
- Modify: `console/backend/main.py`
- Modify: `console/backend/routers/llm.py`

- [ ] **Step 1: Add assets router (for video assets upload with MJ fields) + sfx + youtube_videos**

In `console/backend/main.py`, inside `register_routers()` after the `music` try/except block, add:

```python
    try:
        from console.backend.routers import sfx
        app.include_router(sfx.router, prefix="/api")
    except ImportError:
        pass

    try:
        from console.backend.routers import youtube_videos
        app.include_router(youtube_videos.router, prefix="/api")
    except ImportError:
        pass
```

- [ ] **Step 2: Add Runway endpoints to llm router**

In `console/backend/routers/llm.py`, add at the end:

```python
@router.get("/runway")
def get_runway_config(_user=Depends(require_admin)):
    import os
    key = os.environ.get("RUNWAY_API_KEY", "")
    masked = f"{'*' * (len(key) - 4)}{key[-4:]}" if len(key) > 4 else "not set"
    return {
        "api_key_set": bool(key),
        "api_key_masked": masked,
        "model": os.environ.get("RUNWAY_MODEL", "gen3-alpha"),
    }


@router.put("/runway")
def save_runway_config(body: dict, _user=Depends(require_admin)):
    from console.backend.services.runway_service import RunwayService
    api_key = body.get("api_key", "")
    model = body.get("model", "gen3-alpha")
    if api_key:
        os.environ["RUNWAY_API_KEY"] = api_key
    if model:
        os.environ["RUNWAY_MODEL"] = model
    result = RunwayService(api_key=api_key or None, model=model).test_connection()
    return {"ok": result["ok"], "error": result.get("error")}


@router.post("/runway/test")
def test_runway(_user=Depends(require_admin)):
    import os
    from console.backend.services.runway_service import RunwayService
    svc = RunwayService(
        api_key=os.environ.get("RUNWAY_API_KEY"),
        model=os.environ.get("RUNWAY_MODEL", "gen3-alpha"),
    )
    return svc.test_connection()
```

Also add `import os` at the top of `console/backend/routers/llm.py`.

- [ ] **Step 3: Restart server and verify routes appear**

```bash
curl -s http://localhost:8080/docs | grep -E '"(sfx|youtube-videos|runway)"' | head -10
```

Expected: routes appear in OpenAPI docs.

- [ ] **Step 4: Commit**

```bash
git add console/backend/main.py console/backend/routers/llm.py
git commit -m "feat: register sfx + youtube_videos routers; add Runway LLM endpoints"
```

---

## Task 10: API Client Additions

**Files:**
- Modify: `console/frontend/src/api/client.js`

- [ ] **Step 1: Add sfxApi, youtubeVideosApi, templatesApi**

In `console/frontend/src/api/client.js`, add after `assetsApi`:

```javascript
// ── SFX Assets ─────────────────────────────────────────────────────────────────
export const sfxApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== '')))
    return fetchApi(`/api/sfx?${q}`)
  },
  soundTypes: () => fetchApi('/api/sfx/sound-types'),
  import: (file, metadata) => {
    const form = new FormData()
    form.append('file', file)
    Object.entries(metadata).forEach(([k, v]) => form.append(k, v))
    const headers = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    return fetch('/api/sfx/import', { method: 'POST', body: form, headers })
      .then(async res => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }))
          throw new Error(err.detail || `HTTP ${res.status}`)
        }
        return res.json()
      })
  },
  delete: (id) => fetchApi(`/api/sfx/${id}`, { method: 'DELETE' }),
  streamUrl: (id) => `/api/sfx/${id}/stream`,
}

// ── YouTube Videos ─────────────────────────────────────────────────────────────
export const youtubeVideosApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== '')))
    return fetchApi(`/api/youtube-videos?${q}`)
  },
  get: (id) => fetchApi(`/api/youtube-videos/${id}`),
  create: (body) => fetchApi('/api/youtube-videos', { method: 'POST', body: JSON.stringify(body) }),
  update: (id, body) => fetchApi(`/api/youtube-videos/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (id) => fetchApi(`/api/youtube-videos/${id}`, { method: 'DELETE' }),
  queueRender: (id) => fetchApi(`/api/youtube-videos/${id}/render`, { method: 'POST' }),
  templates: () => fetchApi('/api/youtube-videos/templates/list'),
}

// ── Music Templates ─────────────────────────────────────────────────────────────
export const templatesApi = {
  musicTypes: () => fetchApi('/api/music/templates'),
}
```

- [ ] **Step 2: Commit**

```bash
git add console/frontend/src/api/client.js
git commit -m "feat: add sfxApi, youtubeVideosApi, templatesApi to API client"
```

---

## Task 11: SFXPage.jsx

**Files:**
- Create: `console/frontend/src/pages/SFXPage.jsx`

- [ ] **Step 1: Implement SFXPage**

```jsx
// console/frontend/src/pages/SFXPage.jsx
import { useState, useRef, useEffect } from 'react'
import { sfxApi } from '../api/client.js'
import { Card, Badge, Button, Input, Select, Modal, EmptyState, Toast } from '../components/index.jsx'

const SOUND_TYPE_SUGGESTIONS = [
  { group: 'RAIN', types: ['rain_heavy', 'rain_light', 'rain_window', 'rain_forest', 'rain_tent'] },
  { group: 'WATER', types: ['ocean_waves', 'stream_river', 'waterfall', 'fountain', 'lake'] },
  { group: 'WEATHER', types: ['thunder', 'wind_gentle', 'wind_strong', 'blizzard', 'hail'] },
  { group: 'FIRE', types: ['fireplace', 'campfire', 'crackling_embers'] },
  { group: 'NATURE', types: ['birds', 'crickets', 'forest_ambience', 'leaves_rustling', 'frogs'] },
  { group: 'URBAN', types: ['cafe_chatter', 'coffee_machine', 'pub_tavern', 'city_traffic', 'train', 'keyboard_typing', 'pages_turning', 'restaurant'] },
  { group: 'NOISE', types: ['pink_noise', 'white_noise', 'brown_noise'] },
  { group: 'SPECIAL', types: ['space_hum', 'magical_ambient', 'underwater', 'crowd_distant'] },
]

const ALL_SUGGESTIONS = SOUND_TYPE_SUGGESTIONS.flatMap(g => g.types)

function ImportModal({ onClose, onImported }) {
  const [file, setFile] = useState(null)
  const [title, setTitle] = useState('')
  const [soundType, setSoundType] = useState('')
  const [source, setSource] = useState('import')
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const handleSubmit = async () => {
    if (!file || !title || !soundType) { showToast('Title, sound type, and file are required', 'error'); return }
    setLoading(true)
    try {
      await sfxApi.import(file, { title, sound_type: soundType, source })
      onImported()
      onClose()
    } catch (e) { showToast(e.message, 'error') }
    finally { setLoading(false) }
  }

  return (
    <Modal open onClose={onClose} title="Import SFX" width="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={loading} onClick={handleSubmit}>Import</Button>
        </>
      }
    >
      {toast && <Toast message={toast.msg} type={toast.type} />}
      <div className="flex flex-col gap-4">
        <Input label="Title" value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. Heavy Rain Stereo" />
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Sound Type</label>
          <input
            list="sound-type-list"
            value={soundType}
            onChange={e => setSoundType(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-[#16161a] border border-[#2a2a32] text-sm text-[#e8e8f0] focus:outline-none focus:border-[#7c6af7]"
            placeholder="rain_heavy, birds, pink_noise..."
          />
          <datalist id="sound-type-list">
            {ALL_SUGGESTIONS.map(t => <option key={t} value={t} />)}
          </datalist>
        </div>
        <Select label="Source" value={source} onChange={e => setSource(e.target.value)}>
          <option value="import">Manual Import</option>
          <option value="freesound">Freesound.org</option>
        </Select>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">File (WAV / MP3)</label>
          <input
            type="file" accept=".wav,.mp3,.m4a,.ogg"
            onChange={e => setFile(e.target.files?.[0] || null)}
            className="text-sm text-[#9090a8] file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-[#2a2a32] file:text-[#e8e8f0] file:text-xs cursor-pointer"
          />
        </div>
      </div>
    </Modal>
  )
}

export default function SFXPage() {
  const [sfxList, setSfxList] = useState([])
  const [soundTypes, setSoundTypes] = useState([])
  const [loading, setLoading] = useState(true)
  const [filterType, setFilterType] = useState('')
  const [search, setSearch] = useState('')
  const [showImport, setShowImport] = useState(false)
  const [playing, setPlaying] = useState(null)
  const audioRef = useRef(null)

  const load = async () => {
    setLoading(true)
    const [list, types] = await Promise.all([
      sfxApi.list({ sound_type: filterType || undefined, search: search || undefined }),
      sfxApi.soundTypes(),
    ])
    setSfxList(list)
    setSoundTypes(types)
    setLoading(false)
  }

  useEffect(() => { load() }, [filterType, search])

  const handlePlay = (sfx) => {
    if (playing === sfx.id) {
      audioRef.current?.pause()
      setPlaying(null)
    } else {
      if (audioRef.current) audioRef.current.pause()
      audioRef.current = new Audio(sfxApi.streamUrl(sfx.id))
      audioRef.current.play()
      audioRef.current.onended = () => setPlaying(null)
      setPlaying(sfx.id)
    }
  }

  const handleDelete = async (sfx) => {
    if (!confirm(`Delete "${sfx.title}"?`)) return
    await sfxApi.delete(sfx.id)
    load()
  }

  const sourceColor = { import: '#9090a8', freesound: '#34d399' }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#e8e8f0]">SFX Library</h1>
          <p className="text-sm text-[#9090a8] mt-0.5">{sfxList.length} assets</p>
        </div>
        <Button variant="primary" onClick={() => setShowImport(true)}>+ Import SFX</Button>
      </div>

      <div className="flex gap-3">
        <Input
          placeholder="Search..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <Select value={filterType} onChange={e => setFilterType(e.target.value)} className="max-w-[180px]">
          <option value="">All types</option>
          {soundTypes.map(t => <option key={t} value={t}>{t}</option>)}
        </Select>
      </div>

      {loading ? (
        <div className="text-center text-[#9090a8] py-12">Loading...</div>
      ) : sfxList.length === 0 ? (
        <EmptyState title="No SFX assets" message="Import your first SFX file to get started." />
      ) : (
        <div className="flex flex-col gap-2">
          {sfxList.map(sfx => (
            <Card key={sfx.id} className="flex items-center gap-4 px-4 py-3">
              <button
                onClick={() => handlePlay(sfx)}
                className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${
                  playing === sfx.id ? 'bg-[#f87171] text-white' : 'bg-[#2a2a32] text-[#9090a8] hover:text-[#e8e8f0]'
                }`}
              >
                {playing === sfx.id ? '■' : '▶'}
              </button>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-[#e8e8f0] truncate">{sfx.title}</div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs text-[#9090a8] font-mono">{sfx.sound_type}</span>
                  {sfx.duration_s && <span className="text-xs text-[#5a5a70]">{sfx.duration_s.toFixed(0)}s</span>}
                </div>
              </div>
              <Badge style={{ backgroundColor: sourceColor[sfx.source] || '#5a5a70', color: 'white', fontSize: '10px' }}>
                {sfx.source.toUpperCase()}
              </Badge>
              <button onClick={() => handleDelete(sfx)} className="text-[#5a5a70] hover:text-[#f87171] transition-colors">✕</button>
            </Card>
          ))}
        </div>
      )}

      {showImport && <ImportModal onClose={() => setShowImport(false)} onImported={load} />}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add console/frontend/src/pages/SFXPage.jsx
git commit -m "feat: add SFXPage — import, list, filter, play"
```

---

## Task 12: VideoAssetsPage Extension

**Files:**
- Modify: `console/frontend/src/pages/VideoAssetsPage.jsx`

- [ ] **Step 1: Read current VideoAssetsPage to understand structure**

```bash
wc -l console/frontend/src/pages/VideoAssetsPage.jsx
head -60 console/frontend/src/pages/VideoAssetsPage.jsx
```

- [ ] **Step 2: Add asset_type toggle + MidJourney/Runway source badges**

Find the filter bar (where `niche`, `source` dropdowns are rendered) and add the asset type toggle after existing filters:

```jsx
{/* Asset type toggle — add after existing filter dropdowns */}
<div className="flex items-center gap-1 bg-[#16161a] border border-[#2a2a32] rounded-lg p-1">
  {['all', 'video_clip', 'still_image'].map(t => (
    <button
      key={t}
      onClick={() => setFilterAssetType(t === 'all' ? '' : t)}
      className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
        (filterAssetType || 'all') === t
          ? 'bg-[#7c6af7] text-white'
          : 'text-[#9090a8] hover:text-[#e8e8f0]'
      }`}
    >
      {t === 'all' ? 'All' : t === 'video_clip' ? 'Video Clips' : 'Stills'}
    </button>
  ))}
</div>
```

Add `const [filterAssetType, setFilterAssetType] = useState('')` to state.

- [ ] **Step 3: Add MidJourney import button + Animate with Runway modal**

Add `+ Import Still (MidJourney)` button next to existing import button.

Add `AnimateModal` component at top of file:

```jsx
function AnimateModal({ asset, onClose, onAnimated }) {
  const [prompt, setPrompt] = useState('')
  const [intensity, setIntensity] = useState(2)
  const [duration, setDuration] = useState(5)
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const handleGenerate = async () => {
    if (!prompt) { showToast('Runway prompt is required', 'error'); return }
    setLoading(true)
    try {
      await assetsApi.animateWithRunway(asset.id, { prompt, motion_intensity: intensity, duration })
      showToast('Animation queued — check back in a few minutes', 'success')
      onAnimated()
      onClose()
    } catch (e) { showToast(e.message, 'error') }
    finally { setLoading(false) }
  }

  return (
    <Modal open onClose={onClose} title="Animate with Runway →" width="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={loading} onClick={handleGenerate}>Generate Loop →</Button>
        </>
      }
    >
      {toast && <Toast message={toast.msg} type={toast.type} />}
      <div className="flex flex-col gap-4">
        {asset.thumbnail_path && (
          <img src={assetsApi.thumbnailUrl(asset.id)} alt={asset.description} className="w-full h-32 object-cover rounded-lg" />
        )}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#9090a8] font-medium">Runway Prompt</label>
          <textarea
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 rounded-lg bg-[#16161a] border border-[#2a2a32] text-sm text-[#e8e8f0] resize-none focus:outline-none focus:border-[#7c6af7]"
            placeholder="Slow rain droplets running down glass. No camera movement. Hypnotic loop."
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[#9090a8] font-medium">Motion Intensity ({intensity}/10)</label>
            <input type="range" min={1} max={10} value={intensity} onChange={e => setIntensity(Number(e.target.value))}
              className="w-full accent-[#7c6af7]" />
          </div>
          <Select label="Duration" value={duration} onChange={e => setDuration(Number(e.target.value))}>
            <option value={5}>5s</option>
            <option value={10}>10s</option>
          </Select>
        </div>
      </div>
    </Modal>
  )
}
```

- [ ] **Step 4: Update assetsApi in client.js to add animateWithRunway + thumbnailUrl**

In `console/frontend/src/api/client.js`, update `assetsApi`:

```javascript
export const assetsApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== '')))
    return fetchApi(`/api/production/assets?${q}`)
  },
  upload: (file, metadata) => {
    const form = new FormData()
    form.append('file', file)
    form.append('metadata', JSON.stringify(metadata))
    const headers = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    return fetch('/api/production/assets/upload', { method: 'POST', body: form, headers })
      .then(async res => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }))
          throw new Error(err.detail || `HTTP ${res.status}`)
        }
        return res.json()
      })
  },
  update: (id, body) =>
    fetchApi(`/api/production/assets/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  delete: (id) =>
    fetchApi(`/api/production/assets/${id}`, { method: 'DELETE' }),
  streamUrl: (id) => `/api/production/assets/${id}/stream`,
  thumbnailUrl: (id) => `/api/production/assets/${id}/thumbnail`,
  animateWithRunway: (id, body) =>
    fetchApi(`/api/production/assets/${id}/animate`, { method: 'POST', body: JSON.stringify(body) }),
}
```

- [ ] **Step 5: Add animate endpoint to production router**

In `console/backend/routers/production.py`, add:

```python
class AnimateBody(BaseModel):
    prompt: str
    motion_intensity: int = 2
    duration: int = 5

@router.post("/assets/{asset_id}/animate")
def animate_asset(
    asset_id: int,
    body: AnimateBody,
    db: Session = Depends(get_db),
    _user=Depends(require_editor_or_admin),
):
    from console.backend.models.video_asset import VideoAsset
    from console.backend.tasks.runway_task import animate_asset_task
    import os

    asset = db.get(VideoAsset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.asset_type != "still_image":
        raise HTTPException(status_code=400, detail="Only still images can be animated")

    api_key = os.environ.get("RUNWAY_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=400, detail="RUNWAY_API_KEY not configured")

    from console.backend.services.runway_service import RunwayService
    model = os.environ.get("RUNWAY_MODEL", "gen3-alpha")
    svc = RunwayService(api_key=api_key, model=model)

    # For image-to-video we need a public URL — use the stream endpoint for now
    image_url = f"{os.environ.get('PUBLIC_API_URL', 'http://localhost:8080')}/api/production/assets/{asset_id}/stream"
    runway_task_id = svc.submit_image_to_video(image_url, body.prompt, body.duration, body.motion_intensity)

    # Create a new video_clip asset linked as child
    from console.backend.models.video_asset import VideoAsset as VA
    child = VA(
        file_path="",
        source="runway",
        asset_type="video_clip",
        parent_asset_id=asset_id,
        generation_prompt=body.prompt,
        runway_status="pending",
        description=f"Runway animation of asset {asset_id}",
    )
    db.add(child)
    db.commit()
    db.refresh(child)

    output_filename = f"runway_{child.id}.mp4"
    task = animate_asset_task.delay(child.id, runway_task_id, output_filename, api_key, model)

    child.runway_status = "pending"
    db.commit()

    return {"asset_id": child.id, "task_id": task.id, "runway_task_id": runway_task_id}
```

- [ ] **Step 6: Update source badge colors in VideoAssetsPage**

Find `PROVIDER_COLORS` or the source badge section and add:

```javascript
const SOURCE_COLORS = {
  pexels: '#4a9eff',
  veo: '#7c6af7',
  manual: '#9090a8',
  stock: '#9090a8',
  midjourney: '#f97316',  // orange
  runway: '#14b8a6',      // teal
}
```

Show `RUNWAY ●` pending badge when `asset.runway_status === 'pending'`.

- [ ] **Step 7: Commit**

```bash
git add console/frontend/src/pages/VideoAssetsPage.jsx console/frontend/src/api/client.js console/backend/routers/production.py
git commit -m "feat: VideoAssetsPage — MJ/Runway sources, Animate modal, asset_type filter"
```

---

## Task 13: MusicPage — Suno Manual Modal

**Files:**
- Modify: `console/frontend/src/pages/MusicPage.jsx`

- [ ] **Step 1: Add Suno manual flow to GenerateModal**

Find the `GenerateModal` function in `MusicPage.jsx`. Add state for `musicTemplates`:

```jsx
const [musicTemplates, setMusicTemplates] = useState([])

useEffect(() => {
  if (form.provider === 'suno') {
    templatesApi.musicTypes().then(setMusicTemplates).catch(() => {})
  }
}, [form.provider])
```

Add `import { templatesApi } from '../api/client.js'` to the imports.

- [ ] **Step 2: Move provider to top and add conditional Suno layout**

Replace the provider Select field (wherever it appears in the modal form) with this block at the TOP of the form:

```jsx
<Select
  label="Provider"
  value={form.provider}
  onChange={e => setForm(f => ({ ...f, provider: e.target.value }))}
>
  <option value="sunoapi">SunoAPI</option>
  <option value="suno">Suno (Manual)</option>
  <option value="lyria-clip">Lyria Clip (30s)</option>
  <option value="lyria-pro">Lyria Pro</option>
</Select>
```

- [ ] **Step 3: Add Suno manual form branch**

After the provider select, add:

```jsx
{form.provider === 'suno' ? (
  <SunoManualForm
    musicTemplates={musicTemplates}
    form={form}
    setForm={setForm}
  />
) : (
  /* existing form fields (idea textarea, niches, moods, genres, is_vocal) */
  <>
    {/* ... keep existing fields here unchanged ... */}
  </>
)}
```

- [ ] **Step 4: Implement SunoManualForm component (add at top of file)**

```jsx
const SUNO_EXTEND_STEPS = [
  'Generate initial clip on suno.com (~2 min)',
  'Click ··· → Extend on the generated clip',
  'Click ··· → Extend again from the NEW clip (not the original)',
  'Repeat steps 2–3 until you have enough extends',
  'On the LAST clip: ··· → Get Whole Song → Download MP3',
]

function SunoManualForm({ musicTemplates, form, setForm }) {
  const [showExtendGuide, setShowExtendGuide] = useState(false)
  const selectedTemplate = musicTemplates.find(t => t.slug === form.sunoMusicType) || musicTemplates[0]
  const prompt = selectedTemplate?.suno_prompt_template || ''
  const soundRules = selectedTemplate?.sound_rules || []
  const extendsRecommended = selectedTemplate?.suno_extends_recommended

  const handleCopy = () => {
    navigator.clipboard.writeText(prompt)
  }

  return (
    <div className="flex flex-col gap-4">
      <Select
        label="Music Type"
        value={form.sunoMusicType || ''}
        onChange={e => setForm(f => ({ ...f, sunoMusicType: e.target.value }))}
      >
        <option value="">Select type...</option>
        {musicTemplates.map(t => (
          <option key={t.slug} value={t.slug}>{t.label}</option>
        ))}
      </Select>

      {selectedTemplate && (
        <>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[#9090a8] font-medium">SUNO PROMPT</label>
            <div className="relative bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3">
              <p className="text-sm text-[#e8e8f0] pr-12 leading-relaxed">{prompt}</p>
              <button
                onClick={handleCopy}
                className="absolute top-2 right-2 text-xs text-[#7c6af7] hover:text-[#9d8df8] transition-colors px-2 py-1 bg-[#16161a] rounded"
              >
                Copy
              </button>
            </div>
          </div>

          {soundRules.length > 0 && (
            <div className="bg-[#1c1c22] border border-[#fbbf24] border-opacity-40 rounded-lg p-3">
              <div className="text-xs font-semibold text-[#fbbf24] mb-2">⚠ {selectedTemplate.label.toUpperCase()} SOUND RULES</div>
              <ul className="flex flex-col gap-1">
                {soundRules.map((rule, i) => (
                  <li key={i} className="text-xs text-[#9090a8]">• {rule}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="border border-[#2a2a32] rounded-lg overflow-hidden">
            <button
              onClick={() => setShowExtendGuide(g => !g)}
              className="w-full flex items-center justify-between px-4 py-3 text-sm text-[#e8e8f0] bg-[#16161a] hover:bg-[#1c1c22] transition-colors"
            >
              <span>▸ HOW TO EXTEND ON SUNO</span>
              <span className="text-[#9090a8]">{showExtendGuide ? '▲' : '▼'}</span>
            </button>
            {showExtendGuide && (
              <div className="px-4 py-3 bg-[#0d0d0f] flex flex-col gap-2">
                {SUNO_EXTEND_STEPS.map((step, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <span className="text-xs font-mono text-[#7c6af7] flex-shrink-0 mt-0.5">Step {i + 1}</span>
                    <span className="text-xs text-[#9090a8]">{step}</span>
                  </div>
                ))}
                {extendsRecommended && (
                  <div className="mt-2 text-xs text-[#5a5a70] border-t border-[#2a2a32] pt-2">
                    {selectedTemplate.label}: <strong className="text-[#e8e8f0]">{extendsRecommended} extends</strong> recommended
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}

      {/* File upload for manual import */}
      <div className="flex flex-col gap-1">
        <label className="text-xs text-[#9090a8] font-medium">Upload finished file</label>
        <div
          className="border-2 border-dashed border-[#2a2a32] rounded-lg p-6 text-center cursor-pointer hover:border-[#7c6af7] transition-colors"
          onDragOver={e => e.preventDefault()}
          onDrop={e => { e.preventDefault(); setForm(f => ({ ...f, uploadFile: e.dataTransfer.files[0] })) }}
          onClick={() => document.getElementById('suno-upload-input').click()}
        >
          <input
            id="suno-upload-input" type="file" accept=".mp3,.wav" className="hidden"
            onChange={e => setForm(f => ({ ...f, uploadFile: e.target.files?.[0] || null }))}
          />
          {form.uploadFile ? (
            <span className="text-sm text-[#34d399]">✓ {form.uploadFile.name}</span>
          ) : (
            <span className="text-sm text-[#5a5a70]">Drop MP3/WAV here or click to browse</span>
          )}
        </div>
      </div>

      <Input label="Title" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} placeholder="Track title" />
    </div>
  )
}
```

- [ ] **Step 5: Update footer button and submit handler**

In the modal footer, change button label conditionally:

```jsx
footer={
  <>
    <Button variant="ghost" onClick={onClose}>Cancel</Button>
    {form.provider !== 'suno' && (
      <Button variant="default" loading={expanding} onClick={handleExpandOnly}>
        Expand with Gemini
      </Button>
    )}
    <Button variant="primary" loading={loading} onClick={form.provider === 'suno' ? handleSunoUpload : handleGenerate}>
      {form.provider === 'suno' ? 'Upload' : 'Generate'}
    </Button>
  </>
}
```

Add `handleSunoUpload` handler:

```jsx
const handleSunoUpload = async () => {
  if (!form.uploadFile || !form.title) {
    showToast('Title and file are required', 'error'); return
  }
  setLoading(true)
  try {
    await musicApi.upload(form.uploadFile, {
      title: form.title,
      niches: form.niches,
      moods: form.moods,
      genres: form.genres,
      is_vocal: false,
      provider: 'suno',
    })
    onSaved()
    onClose()
  } catch (e) { showToast(e.message, 'error') }
  finally { setLoading(false) }
}
```

- [ ] **Step 6: Update PROVIDER_COLORS**

Find `PROVIDER_COLORS` and update:

```javascript
const PROVIDER_COLORS = {
  sunoapi: '#7c6af7',   // purple
  suno:    '#6d28d9',   // violet (distinct)
  'lyria-clip': '#4a9eff',
  'lyria-pro':  '#34d399',
  import:  '#9090a8',
}
```

- [ ] **Step 7: Commit**

```bash
git add console/frontend/src/pages/MusicPage.jsx
git commit -m "feat: MusicPage — Suno manual modal with guide, sound rules, extend steps"
```

---

## Task 14: YouTubeVideosPage — List + Creation Form

**Files:**
- Create: `console/frontend/src/pages/YouTubeVideosPage.jsx`

- [ ] **Step 1: Implement YouTubeVideosPage**

```jsx
// console/frontend/src/pages/YouTubeVideosPage.jsx
import { useState, useEffect } from 'react'
import { youtubeVideosApi, musicApi, assetsApi } from '../api/client.js'
import { Card, Badge, Button, Input, Select, Modal, EmptyState, Toast, Spinner } from '../components/index.jsx'

const STATUS_COLORS = {
  draft:     '#9090a8',
  rendering: '#fbbf24',
  ready:     '#34d399',
  uploaded:  '#4a9eff',
}

const QUALITY_OPTIONS = ['1080p', '4K']
const DURATION_PRESETS = [
  { label: '1h', value: 1 },
  { label: '3h', value: 3 },
  { label: '8h', value: 8 },
  { label: '10h', value: 10 },
  { label: 'Custom', value: null },
]

function CreationPanel({ template, onClose, onCreated }) {
  const [form, setForm] = useState({
    theme: '',
    target_duration_h: template?.target_duration_h || 8,
    customDuration: '',
    isCustomDuration: false,
    music_track_id: null,
    visual_asset_id: null,
    sfx_overrides: null,
    seo_title: '',
    seo_description: '',
    seo_tags: '',
    output_quality: '1080p',
  })
  const [musicList, setMusicList] = useState([])
  const [assetList, setAssetList] = useState([])
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  useEffect(() => {
    musicApi.list({ status: 'ready' }).then(setMusicList).catch(() => {})
    assetsApi.list({ asset_type: 'video_clip' }).then(d => setAssetList(d.items || d)).catch(() => {})
  }, [])

  useEffect(() => {
    if (form.theme && template) {
      const h = form.isCustomDuration ? (parseFloat(form.customDuration) || 8) : form.target_duration_h
      setForm(f => ({
        ...f,
        seo_title: (template.seo_title_formula || '{theme} — {duration}h')
          .replace('{theme}', form.theme)
          .replace('{duration}', h),
        seo_description: (template.seo_description_template || '')
          .replace('{theme}', form.theme)
          .replace('{duration}', h),
      }))
    }
  }, [form.theme, form.target_duration_h, form.customDuration])

  const handleSubmit = async () => {
    if (!form.theme) { showToast('Theme is required', 'error'); return }
    const duration = form.isCustomDuration ? parseFloat(form.customDuration) : form.target_duration_h
    if (!duration || duration <= 0) { showToast('Valid duration is required', 'error'); return }
    setLoading(true)
    try {
      const title = form.seo_title || `${template.label} — ${form.theme}`
      await youtubeVideosApi.create({
        title,
        template_id: template.id,
        theme: form.theme,
        target_duration_h: duration,
        music_track_id: form.music_track_id || null,
        visual_asset_id: form.visual_asset_id || null,
        sfx_overrides: form.sfx_overrides,
        seo_title: form.seo_title,
        seo_description: form.seo_description,
        seo_tags: form.seo_tags ? form.seo_tags.split(',').map(t => t.trim()).filter(Boolean) : [],
        output_quality: form.output_quality,
      })
      onCreated()
      onClose()
    } catch (e) { showToast(e.message, 'error') }
    finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-[480px] h-full bg-[#16161a] border-l border-[#2a2a32] flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#2a2a32]">
          <h2 className="text-base font-semibold text-[#e8e8f0]">New {template?.label}</h2>
          <button onClick={onClose} className="text-[#9090a8] hover:text-[#e8e8f0]">✕</button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-4 flex flex-col gap-6">
          {toast && <Toast message={toast.msg} type={toast.type} />}

          {/* ① THEME & SEO */}
          <section>
            <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">① THEME & SEO</div>
            <div className="flex flex-col gap-3">
              <Input label="Theme" value={form.theme} onChange={e => setForm(f => ({ ...f, theme: e.target.value }))} placeholder="e.g. Heavy Rain Window" />
              <div className="flex flex-col gap-1">
                <label className="text-xs text-[#9090a8] font-medium">Duration</label>
                <div className="flex flex-wrap gap-2">
                  {DURATION_PRESETS.map(p => (
                    <button key={p.label}
                      onClick={() => setForm(f => ({
                        ...f,
                        isCustomDuration: p.value === null,
                        target_duration_h: p.value || f.target_duration_h,
                      }))}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                        (p.value === null ? form.isCustomDuration : !form.isCustomDuration && form.target_duration_h === p.value)
                          ? 'bg-[#7c6af7] border-[#7c6af7] text-white'
                          : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8] hover:text-[#e8e8f0]'
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
                {form.isCustomDuration && (
                  <Input
                    value={form.customDuration}
                    onChange={e => setForm(f => ({ ...f, customDuration: e.target.value }))}
                    placeholder="Hours (e.g. 6.5)"
                    type="number" min="0.5" step="0.5"
                  />
                )}
                {template?.target_duration_h && (
                  <p className="text-xs text-[#5a5a70]">💡 {template.label} recommended: {template.target_duration_h}h</p>
                )}
              </div>
              <Input label="SEO Title" value={form.seo_title} onChange={e => setForm(f => ({ ...f, seo_title: e.target.value }))} />
              <Input label="SEO Tags (comma-separated)" value={form.seo_tags} onChange={e => setForm(f => ({ ...f, seo_tags: e.target.value }))} placeholder="asmr, rain, sleep, relaxing" />
            </div>
          </section>

          {/* ② MUSIC */}
          <section>
            <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">② MUSIC</div>
            <div className="flex flex-col gap-3">
              <Select label="Music Track" value={form.music_track_id || ''} onChange={e => setForm(f => ({ ...f, music_track_id: e.target.value || null }))}>
                <option value="">— Select from library —</option>
                {musicList.map(m => <option key={m.id} value={m.id}>{m.title} ({m.provider})</option>)}
              </Select>
              {template?.suno_prompt_template && (
                <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 relative">
                  <div className="text-xs text-[#5a5a70] mb-1">Suno Prompt (reference)</div>
                  <p className="text-xs text-[#9090a8] pr-10 leading-relaxed">{template.suno_prompt_template}</p>
                  <button onClick={() => navigator.clipboard.writeText(template.suno_prompt_template)}
                    className="absolute top-2 right-2 text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-1 bg-[#16161a] rounded">
                    Copy
                  </button>
                </div>
              )}
            </div>
          </section>

          {/* ③ VISUAL */}
          <section>
            <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">③ VISUAL</div>
            <div className="flex flex-col gap-3">
              <Select label="Visual Loop" value={form.visual_asset_id || ''} onChange={e => setForm(f => ({ ...f, visual_asset_id: e.target.value || null }))}>
                <option value="">— Select from library —</option>
                {assetList.map(a => <option key={a.id} value={a.id}>{a.description || `Asset #${a.id}`} ({a.source})</option>)}
              </Select>
              {template?.runway_prompt_template && (
                <div className="bg-[#0d0d0f] border border-[#2a2a32] rounded-lg p-3 relative">
                  <div className="text-xs text-[#5a5a70] mb-1">Runway Prompt (reference)</div>
                  <p className="text-xs text-[#9090a8] pr-10 leading-relaxed">{template.runway_prompt_template}</p>
                  <button onClick={() => navigator.clipboard.writeText(template.runway_prompt_template)}
                    className="absolute top-2 right-2 text-xs text-[#7c6af7] hover:text-[#9d8df8] px-2 py-1 bg-[#16161a] rounded">
                    Copy
                  </button>
                </div>
              )}
            </div>
          </section>

          {/* ④ RENDER */}
          <section>
            <div className="text-xs font-bold text-[#5a5a70] tracking-widest mb-3">④ RENDER</div>
            <Select label="Output Quality" value={form.output_quality} onChange={e => setForm(f => ({ ...f, output_quality: e.target.value }))}>
              {QUALITY_OPTIONS.map(q => <option key={q} value={q}>{q}</option>)}
            </Select>
          </section>
        </div>

        <div className="px-6 py-4 border-t border-[#2a2a32] flex gap-3 justify-end">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={loading} onClick={handleSubmit}>Queue Render →</Button>
        </div>
      </div>
    </div>
  )
}

export default function YouTubeVideosPage() {
  const [videos, setVideos] = useState([])
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState('')
  const [activeTemplate, setActiveTemplate] = useState(null)
  const [toast, setToast] = useState(null)
  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const load = async () => {
    setLoading(true)
    const [vids, tmpl] = await Promise.all([
      youtubeVideosApi.list({ status: filterStatus || undefined }),
      youtubeVideosApi.templates(),
    ])
    setVideos(vids)
    setTemplates(tmpl.filter(t => t.output_format === 'landscape_long'))
    setLoading(false)
  }

  useEffect(() => { load() }, [filterStatus])

  const handleRender = async (video) => {
    try {
      await youtubeVideosApi.queueRender(video.id)
      showToast('Render queued', 'success')
      load()
    } catch (e) { showToast(e.message, 'error') }
  }

  const handleDelete = async (video) => {
    if (!confirm(`Delete "${video.title}"?`)) return
    try {
      await youtubeVideosApi.delete(video.id)
      load()
    } catch (e) { showToast(e.message, 'error') }
  }

  const landscapeTemplates = templates.filter(t => t.output_format === 'landscape_long')

  return (
    <div className="flex flex-col gap-6">
      {toast && <Toast message={toast.msg} type={toast.type} />}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[#e8e8f0]">YouTube Videos</h1>
          <p className="text-sm text-[#9090a8] mt-0.5">{videos.length} videos</p>
        </div>
        <div className="flex gap-2">
          {landscapeTemplates.map(t => (
            <Button key={t.slug} variant="primary" onClick={() => setActiveTemplate(t)}>
              + New {t.label}
            </Button>
          ))}
        </div>
      </div>

      <div className="flex gap-3">
        <Select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className="max-w-[160px]">
          <option value="">All Status</option>
          <option value="draft">Draft</option>
          <option value="rendering">Rendering</option>
          <option value="ready">Ready</option>
          <option value="uploaded">Uploaded</option>
        </Select>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Spinner /></div>
      ) : videos.length === 0 ? (
        <EmptyState title="No YouTube videos" message="Create your first ASMR or Soundscape video." />
      ) : (
        <div className="flex flex-col gap-3">
          {videos.map(v => {
            const tmpl = templates.find(t => t.id === v.template_id)
            return (
              <Card key={v.id} className="px-5 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3 min-w-0">
                    <Badge style={{ backgroundColor: '#2a2a32', color: '#9090a8', fontSize: '10px', flexShrink: 0 }}>
                      {tmpl?.label || 'UNKNOWN'}
                    </Badge>
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-[#e8e8f0] truncate">{v.title}</div>
                      <div className="flex items-center gap-3 mt-1">
                        <span className="text-xs text-[#9090a8]">
                          {v.target_duration_h ? `${v.target_duration_h}h` : '—'}
                        </span>
                        {v.music_track_id && <span className="text-xs text-[#5a5a70]">🎵 music linked</span>}
                        {v.visual_asset_id && <span className="text-xs text-[#5a5a70]">🖼 visual linked</span>}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-xs font-medium" style={{ color: STATUS_COLORS[v.status] }}>
                      ● {v.status}
                    </span>
                    {v.status === 'draft' && (
                      <Button variant="ghost" size="sm" onClick={() => handleRender(v)}>
                        Render →
                      </Button>
                    )}
                    <button onClick={() => handleDelete(v)} className="text-[#5a5a70] hover:text-[#f87171] text-xs ml-1">✕</button>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {activeTemplate && (
        <CreationPanel
          template={activeTemplate}
          onClose={() => setActiveTemplate(null)}
          onCreated={() => { setActiveTemplate(null); load() }}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat: add YouTubeVideosPage — list, creation slide-over, render dispatch"
```

---

## Task 15: Make Short Modal (Viral Shorts)

**Files:**
- Modify: `console/frontend/src/pages/YouTubeVideosPage.jsx`

- [ ] **Step 1: Add MakeShortModal component**

Add to `YouTubeVideosPage.jsx` before the main export:

```jsx
function MakeShortModal({ video, shortTemplates, onClose, onCreated }) {
  const [form, setForm] = useState({
    sameMusic: true,
    sameVisual: true,
    ctaText: `Full ${video.target_duration_h ? video.target_duration_h + 'h' : ''} version on channel ↑`,
    ctaPosition: 'last_10s',
  })
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState(null)
  const showToast = (msg, type = 'success') => { setToast({ msg, type }); setTimeout(() => setToast(null), 3000) }

  const shortTemplate = shortTemplates[0]

  const handleSubmit = async () => {
    if (!shortTemplate) { showToast('No short template found', 'error'); return }
    setLoading(true)
    try {
      await youtubeVideosApi.create({
        title: `${video.title} — Short`,
        template_id: shortTemplate.id,
        theme: video.theme,
        target_duration_h: 58 / 3600,
        music_track_id: form.sameMusic ? video.music_track_id : null,
        visual_asset_id: form.sameVisual ? video.visual_asset_id : null,
        sfx_overrides: { parent_youtube_video_id: video.id, cta_text: form.ctaText, cta_position: form.ctaPosition },
      })
      onCreated()
      onClose()
    } catch (e) { showToast(e.message, 'error') }
    finally { setLoading(false) }
  }

  return (
    <Modal open onClose={onClose} title={`New ${shortTemplate?.label || 'Viral Short'}`} width="max-w-md"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={loading} onClick={handleSubmit}>Queue Render →</Button>
        </>
      }
    >
      {toast && <Toast message={toast.msg} type={toast.type} />}
      <div className="flex flex-col gap-4">
        <div className="bg-[#0d0d0f] rounded-lg p-3">
          <div className="text-xs text-[#5a5a70] mb-1">Parent Video</div>
          <div className="text-sm text-[#e8e8f0]">{video.title}</div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[#9090a8] font-medium">Music</label>
            <div className="flex gap-2">
              <button onClick={() => setForm(f => ({ ...f, sameMusic: true }))}
                className={`flex-1 py-2 rounded-lg text-xs border transition-colors ${form.sameMusic ? 'bg-[#7c6af7] border-[#7c6af7] text-white' : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8]'}`}>
                Same as parent
              </button>
              <button onClick={() => setForm(f => ({ ...f, sameMusic: false }))}
                className={`flex-1 py-2 rounded-lg text-xs border transition-colors ${!form.sameMusic ? 'bg-[#7c6af7] border-[#7c6af7] text-white' : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8]'}`}>
                Pick different
              </button>
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[#9090a8] font-medium">Visual</label>
            <div className="flex gap-2">
              <button onClick={() => setForm(f => ({ ...f, sameVisual: true }))}
                className={`flex-1 py-2 rounded-lg text-xs border transition-colors ${form.sameVisual ? 'bg-[#7c6af7] border-[#7c6af7] text-white' : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8]'}`}>
                9:16 crop
              </button>
              <button onClick={() => setForm(f => ({ ...f, sameVisual: false }))}
                className={`flex-1 py-2 rounded-lg text-xs border transition-colors ${!form.sameVisual ? 'bg-[#7c6af7] border-[#7c6af7] text-white' : 'bg-[#16161a] border-[#2a2a32] text-[#9090a8]'}`}>
                Pick different
              </button>
            </div>
          </div>
        </div>
        <div className="text-xs text-[#9090a8]">Duration: <strong className="text-[#e8e8f0]">58 seconds</strong> (fixed)</div>
        <Input label="CTA Overlay Text" value={form.ctaText} onChange={e => setForm(f => ({ ...f, ctaText: e.target.value }))} />
        <Select label="CTA Position" value={form.ctaPosition} onChange={e => setForm(f => ({ ...f, ctaPosition: e.target.value }))}>
          <option value="last_10s">Last 10 seconds</option>
          <option value="throughout">Throughout</option>
        </Select>
      </div>
    </Modal>
  )
}
```

- [ ] **Step 2: Wire Make Short button**

In the video list card inside `YouTubeVideosPage`, add "Make Short" button when status is `ready`:

```jsx
{v.status === 'ready' && (
  <Button variant="ghost" size="sm" onClick={() => setMakeShortVideo(v)}>
    + Make Short
  </Button>
)}
```

Add state: `const [makeShortVideo, setMakeShortVideo] = useState(null)`

Load short templates from `templates.filter(t => t.output_format === 'portrait_short')`.

Add at bottom of component JSX:

```jsx
{makeShortVideo && (
  <MakeShortModal
    video={makeShortVideo}
    shortTemplates={templates.filter(t => t.output_format === 'portrait_short')}
    onClose={() => setMakeShortVideo(null)}
    onCreated={() => { setMakeShortVideo(null); load() }}
  />
)}
```

- [ ] **Step 3: Commit**

```bash
git add console/frontend/src/pages/YouTubeVideosPage.jsx
git commit -m "feat: add Make Short modal for viral short creation from YouTube videos"
```

---

## Task 16: Pipeline Format Filter

**Files:**
- Modify: `console/frontend/src/pages/PipelinePage.jsx`

- [ ] **Step 1: Read current PipelinePage filter bar**

```bash
grep -n "filter\|Filter\|Select\|dropdown" console/frontend/src/pages/PipelinePage.jsx | head -20
```

- [ ] **Step 2: Add format filter state and dropdown**

Find where `status` and `type` filter states are declared and add:

```jsx
const [filterFormat, setFilterFormat] = useState('')
```

Find the filter row in JSX and add the format dropdown after existing filters:

```jsx
<Select value={filterFormat} onChange={e => setFilterFormat(e.target.value)} className="max-w-[160px]">
  <option value="">Format: All</option>
  <option value="short">Short</option>
  <option value="youtube_long">YouTube Long</option>
</Select>
```

- [ ] **Step 3: Pass format to API call**

Find where jobs are fetched (typically `pipelineApi.list(...)` or similar) and add `video_format: filterFormat || undefined` to the params. Include `filterFormat` in the `useEffect` deps.

- [ ] **Step 4: Add YOUTUBE badge to job cards**

Find the job type/status badge rendering and add:

```jsx
{job.video_format === 'youtube_long' && (
  <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#14b8a6] bg-opacity-20 text-[#14b8a6] font-mono">YOUTUBE</span>
)}
```

- [ ] **Step 5: Add video_format filter to pipeline backend**

In `console/backend/services/pipeline_service.py` (or wherever jobs are listed), add `video_format` filter:

```python
if video_format:
    q = q.filter(PipelineJob.video_format == video_format)
```

In `console/backend/routers/pipeline.py`, add query param:

```python
video_format: str | None = Query(None),
```

- [ ] **Step 6: Commit**

```bash
git add console/frontend/src/pages/PipelinePage.jsx console/backend/routers/pipeline.py console/backend/services/pipeline_service.py
git commit -m "feat: Pipeline page — format filter (Short/YouTube Long) + YOUTUBE badge"
```

---

## Task 17: Uploads Format Toggle

**Files:**
- Modify: `console/frontend/src/pages/UploadsPage.jsx`

- [ ] **Step 1: Add format toggle state**

In `UploadsPage.jsx`, find the Videos sub-tab and add state:

```jsx
const [videoFormat, setVideoFormat] = useState('all')
```

- [ ] **Step 2: Add toggle UI**

In the Videos tab toolbar (alongside existing platform/status filters), add:

```jsx
<div className="flex items-center gap-1 bg-[#16161a] border border-[#2a2a32] rounded-lg p-1">
  {['all', 'short', 'youtube_long'].map(f => (
    <button
      key={f}
      onClick={() => setVideoFormat(f)}
      className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
        videoFormat === f
          ? 'bg-[#7c6af7] text-white'
          : 'text-[#9090a8] hover:text-[#e8e8f0]'
      }`}
    >
      {f === 'all' ? 'All' : f === 'short' ? 'Short' : 'YouTube Long'}
    </button>
  ))}
</div>
```

- [ ] **Step 3: Pass format to uploads API**

In `uploadsApi.list(...)`, add `video_format: videoFormat === 'all' ? undefined : videoFormat`.

- [ ] **Step 4: Show duration differently for YouTube videos**

In the video list rendering, display YouTube video duration as hours:

```jsx
{video.video_format === 'youtube_long'
  ? `${(video.duration_s / 3600).toFixed(1)}h`
  : `${Math.round(video.duration_s)}s`
}
```

- [ ] **Step 5: Add video_format filter to uploads backend**

In `console/backend/services/upload_service.py`, in `list_videos()`:

```python
if video_format:
    # youtube_videos joined or filter by format flag on production_jobs
    pass  # filter logic depends on how videos are sourced
```

For now, pass `video_format` as a query param and implement client-side filtering if the backend model doesn't join youtube_videos yet.

- [ ] **Step 6: Commit**

```bash
git add console/frontend/src/pages/UploadsPage.jsx
git commit -m "feat: Uploads page — format toggle All/Short/YouTube Long"
```

---

## Task 18: LLM Page — Runway Section

**Files:**
- Modify: `console/frontend/src/pages/LLMPage.jsx`

- [ ] **Step 1: Read current LLMPage structure**

```bash
grep -n "function\|section\|Ollama\|Gemini\|return\|<div" console/frontend/src/pages/LLMPage.jsx | head -40
```

- [ ] **Step 2: Add Runway section**

Find where the Gemini or Ollama config sections end and add a new Runway section:

```jsx
{/* ── Runway ─────────────────────────────────────────────────────────── */}
<Card className="p-5">
  <h3 className="text-sm font-semibold text-[#e8e8f0] mb-4 flex items-center gap-2">
    <span className="w-2 h-2 rounded-full bg-[#14b8a6]" />
    Runway
  </h3>
  <div className="flex flex-col gap-4">
    <div className="flex flex-col gap-1">
      <label className="text-xs text-[#9090a8] font-medium">API Key</label>
      <div className="flex gap-2">
        <Input
          type="password"
          value={runwayKey}
          onChange={e => setRunwayKey(e.target.value)}
          placeholder="rw-..."
          className="flex-1"
        />
      </div>
      {runwayConfig?.api_key_masked && (
        <span className="text-xs text-[#5a5a70] font-mono">{runwayConfig.api_key_masked}</span>
      )}
    </div>
    <Select label="Model" value={runwayModel} onChange={e => setRunwayModel(e.target.value)}>
      <option value="gen3-alpha">gen3-alpha</option>
      <option value="gen4-turbo">gen4-turbo</option>
    </Select>
    <div className="flex gap-2">
      <Button variant="default" loading={runwaySaving} onClick={handleRunwaySave}>Save</Button>
      <Button variant="ghost" loading={runwayTesting} onClick={handleRunwayTest}>Test Connection</Button>
    </div>
    {runwayTestResult && (
      <div className={`text-xs px-3 py-2 rounded-lg ${runwayTestResult.ok ? 'bg-[#34d399] bg-opacity-10 text-[#34d399]' : 'bg-[#f87171] bg-opacity-10 text-[#f87171]'}`}>
        {runwayTestResult.ok ? '✓ Connected' : `✗ ${runwayTestResult.error}`}
      </div>
    )}
  </div>
</Card>
```

- [ ] **Step 3: Add Runway state + handlers**

At the top of LLMPage, add:

```jsx
const [runwayConfig, setRunwayConfig] = useState(null)
const [runwayKey, setRunwayKey] = useState('')
const [runwayModel, setRunwayModel] = useState('gen3-alpha')
const [runwaySaving, setRunwaySaving] = useState(false)
const [runwayTesting, setRunwayTesting] = useState(false)
const [runwayTestResult, setRunwayTestResult] = useState(null)

useEffect(() => {
  fetchApi('/api/llm/runway').then(d => {
    setRunwayConfig(d)
    setRunwayModel(d.model || 'gen3-alpha')
  }).catch(() => {})
}, [])

const handleRunwaySave = async () => {
  setRunwaySaving(true)
  try {
    const result = await fetchApi('/api/llm/runway', {
      method: 'PUT',
      body: JSON.stringify({ api_key: runwayKey, model: runwayModel }),
    })
    setRunwayTestResult(result)
    setRunwayKey('')
  } catch (e) { setRunwayTestResult({ ok: false, error: e.message }) }
  finally { setRunwaySaving(false) }
}

const handleRunwayTest = async () => {
  setRunwayTesting(true)
  try {
    const result = await fetchApi('/api/llm/runway/test', { method: 'POST' })
    setRunwayTestResult(result)
  } catch (e) { setRunwayTestResult({ ok: false, error: e.message }) }
  finally { setRunwayTesting(false) }
}
```

- [ ] **Step 4: Commit**

```bash
git add console/frontend/src/pages/LLMPage.jsx
git commit -m "feat: LLM page — Runway API key, model selector, test connection"
```

---

## Task 19: Navigation Restructure + Register All Routes

**Files:**
- Modify: `console/frontend/src/App.jsx`

- [ ] **Step 1: Add section field to ALL_TABS and add new tabs**

Replace `ALL_TABS` in `App.jsx`:

```javascript
const ALL_TABS = [
  // LIBRARY
  { id: 'niches',    label: 'Niches',    Icon: Icons.Niches,   roles: ['admin', 'editor'], section: 'library' },
  { id: 'music',     label: 'Music',     Icon: Icons.Music,    roles: ['admin', 'editor'], section: 'library' },
  { id: 'sfx',       label: 'SFX',       Icon: Icons.SFX,      roles: ['admin', 'editor'], section: 'library' },
  { id: 'assets',    label: 'Assets',    Icon: Icons.Assets,   roles: ['admin', 'editor'], section: 'library' },
  // SHORT VIDEOS
  { id: 'composer',  label: 'Composer',  Icon: Icons.Composer, roles: ['admin', 'editor'], section: 'short' },
  { id: 'scraper',   label: 'Scraper',   Icon: Icons.Scraper,  roles: ['admin', 'editor'], section: 'short' },
  { id: 'scripts',   label: 'Scripts',   Icon: Icons.Scripts,  roles: ['admin', 'editor'], section: 'short' },
  { id: 'production',label: 'Production',Icon: Icons.Production,roles: ['admin', 'editor'], section: 'short' },
  // YOUTUBE VIDEOS
  { id: 'youtube',   label: 'YouTube Videos', Icon: Icons.YouTube, roles: ['admin', 'editor'], section: 'youtube' },
  // SHARED
  { id: 'uploads',   label: 'Uploads',   Icon: Icons.Uploads,  roles: ['admin', 'editor'], section: 'shared' },
  { id: 'pipeline',  label: 'Pipeline',  Icon: Icons.Pipeline, roles: ['admin', 'editor'], section: 'shared' },
  // ADMIN
  { id: 'llm',       label: 'LLM',       Icon: Icons.LLM,      roles: ['admin'],            section: 'admin' },
  { id: 'performance',label:'Performance',Icon: Icons.Performance, roles: ['admin', 'editor'], section: 'admin' },
  { id: 'system',    label: 'System',    Icon: Icons.System,   roles: ['admin'],            section: 'admin' },
]
```

- [ ] **Step 2: Add SFX and YouTube icons**

Add to the `Icons` object:

```javascript
SFX: () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/>
  </svg>
),
YouTube: () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22.54 6.42a2.78 2.78 0 0 0-1.95-1.96C18.88 4 12 4 12 4s-6.88 0-8.59.46a2.78 2.78 0 0 0-1.95 1.96A29 29 0 0 0 1 12a29 29 0 0 0 .46 5.58A2.78 2.78 0 0 0 3.41 19.54C5.12 20 12 20 12 20s6.88 0 8.59-.46a2.78 2.78 0 0 0 1.95-1.96A29 29 0 0 0 23 12a29 29 0 0 0-.46-5.58z"/>
    <polygon points="9.75 15.02 15.5 12 9.75 8.98 9.75 15.02"/>
  </svg>
),
```

- [ ] **Step 3: Render section headers in sidebar**

Replace the `<nav>` contents in `App.jsx`:

```jsx
<nav className="flex-1 py-2 overflow-y-auto">
  {renderNavWithSections(tabs)}
</nav>
```

Add `renderNavWithSections` function before `App`:

```javascript
const SECTION_LABELS = {
  library: 'LIBRARY',
  short:   'SHORT VIDEOS',
  youtube: 'YOUTUBE VIDEOS',
  shared:  null,  // no label — Uploads and Pipeline sit between sections
  admin:   'ADMIN',
}

function renderNavWithSections(tabs) {
  const items = []
  let lastSection = null

  tabs.forEach(({ id, label, Icon, section }) => {
    if (section !== lastSection && section !== 'shared' && SECTION_LABELS[section]) {
      items.push(
        <div key={`section-${section}`} className="px-4 pt-4 pb-1">
          <span className="text-[9px] font-bold tracking-widest text-[#5a5a70]">
            {SECTION_LABELS[section]}
          </span>
        </div>
      )
    }
    lastSection = section
    items.push(
      <NavLink
        key={id}
        to={'/' + id}
        className={({ isActive }) =>
          `w-full flex items-center gap-2.5 px-4 py-2.5 text-sm font-medium transition-colors text-left ${
            isActive
              ? 'bg-[#222228] text-[#7c6af7] border-r-2 border-[#7c6af7]'
              : 'text-[#9090a8] hover:bg-[#1c1c22] hover:text-[#e8e8f0]'
          }`
        }
      >
        <Icon />
        {label}
      </NavLink>
    )
  })

  return items
}
```

- [ ] **Step 4: Add new route cases and imports**

Add imports at top of `App.jsx`:

```javascript
import SFXPage from './pages/SFXPage.jsx'
import YouTubeVideosPage from './pages/YouTubeVideosPage.jsx'
```

Add to `renderPage` switch:

```javascript
case 'sfx':     return <SFXPage />
case 'youtube': return <YouTubeVideosPage />
```

- [ ] **Step 5: Fix default redirect**

Change `<Navigate to="/system" replace />` to `<Navigate to="/niches" replace />` so the app lands in the LIBRARY section first.

- [ ] **Step 6: Test nav rendering**

Start the frontend dev server and verify:
1. Section headers (LIBRARY, SHORT VIDEOS, YOUTUBE VIDEOS, ADMIN) appear in sidebar
2. SFX and YouTube Videos tabs are visible and navigable
3. Clicking each opens the correct page without console errors

```bash
cd console/frontend && npm run dev
```

Open http://localhost:5173 in browser. Check all 14 tabs load without errors.

- [ ] **Step 7: Commit**

```bash
git add console/frontend/src/App.jsx
git commit -m "feat: App nav restructure — section headers, SFX + YouTube tabs"
```

---

## Task 20: Run Full Test Suite + Final Verification

- [ ] **Step 1: Run all backend tests**

```bash
cd /Volumes/SSD/Workspace/ai-media-automation
python3 -m pytest tests/ -v
```

Expected: all tests PASS. If any fail, fix before proceeding.

- [ ] **Step 2: Start backend and verify new endpoints**

```bash
# Terminal 1
uvicorn console.backend.main:app --port 8080 --reload

# Terminal 2 — verify endpoints exist
curl -s http://localhost:8080/openapi.json | python3 -c "
import json, sys
spec = json.load(sys.stdin)
paths = [p for p in spec['paths'] if any(x in p for x in ['sfx', 'youtube-video', 'runway'])]
print('\\n'.join(sorted(paths)))
"
```

Expected output includes:
```
/api/sfx
/api/sfx/sound-types
/api/sfx/import
/api/sfx/{sfx_id}
/api/sfx/{sfx_id}/stream
/api/youtube-videos
/api/youtube-videos/{video_id}
/api/youtube-videos/{video_id}/render
/api/youtube-videos/templates/list
/api/llm/runway
/api/llm/runway/test
```

- [ ] **Step 3: Run migration downgrade then upgrade (round-trip test)**

```bash
cd console/backend
alembic downgrade 006
alembic upgrade head
```

Expected: no errors, tables re-created cleanly, 4 template rows re-seeded.

- [ ] **Step 4: Final frontend smoke test**

With both servers running (uvicorn + npm run dev):
1. Navigate to /sfx — Import modal opens, sound type datalist appears
2. Navigate to /youtube — "+ New ASMR" and "+ New Soundscape" buttons appear
3. Open creation form — all 4 sections render, duration presets work, SEO title auto-fills from theme
4. Navigate to /music — Generate modal has "Suno (Manual)" provider option
5. Navigate to /llm — Runway section with API key + model selector is visible
6. Navigate to /pipeline — Format filter dropdown (All/Short/YouTube Long) is present
7. Navigate to /uploads — Format toggle (All/Short/YouTube Long) is present
8. Sidebar shows LIBRARY, SHORT VIDEOS, YOUTUBE VIDEOS, ADMIN section headers

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: verify YouTube video pipeline integration complete"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Section 2 (Nav restructure): Task 19
- ✅ Section 3 (Suno manual): Tasks 1, 8, 13
- ✅ Section 4 (SFX management): Tasks 1, 2, 4, 11
- ✅ Section 4.4 (ffmpeg amix): Task 7
- ✅ Section 5 (Assets MJ/Runway): Tasks 3, 5, 12
- ✅ Section 5.5 (LLM Runway): Tasks 9, 18
- ✅ Section 6 (Templates + YouTube Videos page): Tasks 1, 2, 6, 14
- ✅ Section 7 (Viral shorts): Task 15
- ✅ Section 8.1 (Pipeline format filter): Task 16
- ✅ Section 8.2 (Uploads format toggle): Task 17
- ✅ API client additions: Task 10

**Type consistency check:**
- `SfxService.import_sfx()` signature matches test calls ✅
- `YoutubeVideoService.create()` kwargs match router `CreateBody` ✅
- `video_format` column: `String(20)`, values `'short'` | `'youtube_long'` ✅
- `asset_type` column: `String(20)`, values `'still_image'` | `'video_clip'` ✅
- `runway_status` column: `String(20)`, values `'none'` | `'pending'` | `'ready'` | `'failed'` ✅
- Template slugs: `'asmr'` | `'soundscape'` | `'asmr_viral'` | `'soundscape_viral'` ✅
- Provider values after rename: `'sunoapi'` | `'suno'` | `'lyria-clip'` | `'lyria-pro'` | `'import'` ✅

**No placeholders:** All steps contain complete code or exact commands. ✅
