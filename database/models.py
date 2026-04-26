"""
Core pipeline SQLAlchemy models.
Shared PostgreSQL instance with the Management Console.
"""
from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Table, Text, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()

Table(
    "console_users",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    extend_existing=True,
)


class MusicTrack(Base):
    """Background music tracks — generated via Suno/Lyria or imported."""
    __tablename__ = "music_tracks"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    title             = Column(String(200), nullable=False)
    file_path         = Column(String(500))
    duration_s        = Column(Float)
    niches            = Column(ARRAY(String), default=list)
    moods             = Column(ARRAY(String), default=list)
    genres            = Column(ARRAY(String), default=list)
    is_vocal          = Column(Boolean, default=False)
    is_favorite       = Column(Boolean, default=False)
    volume            = Column(Float, default=0.15)
    usage_count       = Column(Integer, default=0)
    quality_score     = Column(Integer, default=80)
    provider          = Column(String(20))   # suno | lyria-clip | lyria-pro | import
    provider_task_id  = Column(String(200))
    generation_status = Column(String(20), default="pending")  # pending | ready | failed
    generation_prompt = Column(Text)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())


class ViralVideo(Base):
    """Scraped TikTok videos used as RAG context for script generation."""
    __tablename__ = "viral_videos"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    video_id      = Column(String, unique=True, nullable=False)   # platform-specific ID
    source        = Column(String, nullable=False)                 # tiktok_research | tiktok_playwright | apify
    author        = Column(String)
    hook_text     = Column(Text)                                   # first line / first 3s caption
    play_count    = Column(BigInteger, default=0)
    like_count    = Column(BigInteger, default=0)
    share_count   = Column(BigInteger, default=0)
    comment_count = Column(BigInteger, default=0)
    duration_s    = Column(Float)
    niche         = Column(String)
    region        = Column(String, default="vn")
    tags          = Column(ARRAY(String))
    thumbnail_url = Column(String)
    video_url     = Column(String)
    indexed_at    = Column(DateTime(timezone=True))               # when indexed in ChromaDB
    scraped_at    = Column(DateTime(timezone=True), server_default=func.now())
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    @property
    def engagement_rate(self) -> float:
        if not self.play_count:
            return 0.0
        interactions = (self.like_count or 0) + (self.comment_count or 0) + (self.share_count or 0)
        return round(interactions / self.play_count * 100, 2)


class GeneratedScript(Base):
    """
    LLM-generated video scripts.
    Core columns defined here; console extensions added by migration 001.
    """
    __tablename__ = "generated_scripts"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    topic            = Column(String, nullable=False)
    niche            = Column(String)
    template         = Column(String)
    region           = Column(String, default="vn")
    script_json      = Column(JSONB, nullable=False)             # full script structure
    llm_used         = Column(String)                            # qwen2.5:3b | gemini-2.5-flash
    source_video_ids = Column(ARRAY(Integer))                    # ViralVideo IDs used as RAG context
    output_path      = Column(Text)                              # path to video_final.mp4
    # Console extensions (added by migration 001)
    status           = Column(String, default="draft")
    editor_notes     = Column(Text)
    edited_by        = Column(Integer, ForeignKey("console_users.id"), nullable=True)
    approved_at      = Column(DateTime(timezone=True))
    # Feedback extensions (added by migration 003)
    quality_score    = Column(Float)
    platform_video_id = Column(String)                           # YouTube/TikTok video ID after upload
    # Language extension (added by migration 004)
    language         = Column(String, default="vietnamese")
    # Music extension (added by migration 006)
    music_track_id   = Column(Integer, ForeignKey("music_tracks.id"), nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    updated_at       = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class VideoAsset(Base):
    """
    Video clip library — stores metadata for all clips (Pexels, Veo, manual).
    Files live on disk at ASSET_DB_PATH. Base columns from migration 002;
    extended columns added by migration 003.
    """
    __tablename__ = "video_assets"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    file_path     = Column(Text, nullable=False)                 # /assets/video_db/{source}/{hash}.mp4
    file_hash     = Column(String, unique=True)                  # SHA256 of file content
    thumbnail_path = Column(Text)
    source        = Column(String)                               # pexels | veo | manual
    source_id     = Column(String)                               # Pexels video ID or Veo op ID
    veo_prompt    = Column(Text)                                 # full prompt used (Veo only)
    keywords      = Column(ARRAY(String))
    niche         = Column(ARRAY(String))
    tags          = Column(ARRAY(String))
    description   = Column(Text)
    duration_s    = Column(Float)
    resolution    = Column(String)                               # '1080x1920'
    aspect_ratio  = Column(String, default="9:16")
    fps           = Column(Integer, default=30)
    file_size_mb  = Column(Float)
    usage_count   = Column(Integer, default=0)
    last_used_at  = Column(DateTime(timezone=True))
    quality_score = Column(Float, default=0.0)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    expires_at    = Column(DateTime(timezone=True))              # NULL = permanent


class NewsArticle(Base):
    """Scraped news articles from newspaper sources."""
    __tablename__ = "news_articles"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    article_id    = Column(String, unique=True, nullable=False)    # sha256(url)[:16]
    source        = Column(String, nullable=False)                  # vnexpress | tinhte | cnn
    url           = Column(String, unique=True, nullable=False)
    title         = Column(Text, nullable=False)
    main_content  = Column(Text)
    language      = Column(String, nullable=False, default="vietnamese")
    author        = Column(String)
    published_at  = Column(DateTime(timezone=True), nullable=True)
    niche         = Column(String)
    tags          = Column(ARRAY(String))
    thumbnail_url = Column(String)
    indexed_at    = Column(DateTime(timezone=True), nullable=True)
    scraped_at    = Column(DateTime(timezone=True), server_default=func.now())
    created_at    = Column(DateTime(timezone=True), server_default=func.now())


class ViralPattern(Base):
    """Extracted viral content patterns per niche/region from trend analysis."""
    __tablename__ = "viral_patterns"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    niche            = Column(String, nullable=False)
    region           = Column(String, default="vn")
    hook_templates   = Column(ARRAY(String))                     # ["Bạn có biết ...", "5 bí quyết ..."]
    scene_types      = Column(ARRAY(String))                     # ["hook", "problem", "solution", "cta"]
    cta_phrases      = Column(ARRAY(String))                     # ["Theo dõi để ...", "Comment ..."]
    hashtag_clusters = Column(ARRAY(String))                     # top hashtags for this niche
    avg_duration_s   = Column(Float)
    avg_play_count   = Column(BigInteger)
    sample_count     = Column(Integer, default=0)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    updated_at       = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MusicTrack(Base):
    """Background music library with niche/mood/genre metadata and generation tracking."""
    __tablename__ = "music_tracks"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    title             = Column(String, nullable=False)
    file_path         = Column(Text, nullable=True)              # path to audio file (NULL while pending)
    duration_s        = Column(Float, nullable=True)             # seconds
    niches            = Column(ARRAY(String))                    # ["fitness", "wellness"]
    moods             = Column(ARRAY(String))                    # ["energetic", "calm"]
    genres            = Column(ARRAY(String))                    # ["pop", "electronic"]
    is_vocal          = Column(Boolean, default=False)
    is_favorite       = Column(Boolean, default=False)
    volume            = Column(Float, default=0.15)              # 0.0-1.0
    usage_count       = Column(Integer, default=0)
    quality_score     = Column(Float, default=0.0)               # 0-100
    provider          = Column(String, default="import")         # import | suno | lyria | musico
    provider_task_id  = Column(String, nullable=True)            # async task ID
    generation_status = Column(String, default="ready")          # pending | ready | failed
    generation_prompt = Column(Text, nullable=True)              # full prompt used for generation
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    updated_at        = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
