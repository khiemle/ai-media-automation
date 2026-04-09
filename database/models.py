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
