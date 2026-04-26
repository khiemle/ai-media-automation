"""
Video Asset Database — search + write-back layer.
PostgreSQL metadata + local file system storage.
Score-based matching: keyword overlap normalized by asset keyword count.
"""
import hashlib
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_root = Path(__file__).parent.parent
load_dotenv(_root / ".env", override=False)

logger = logging.getLogger(__name__)

ASSET_DB_PATH = os.environ.get("ASSET_DB_PATH", "./assets/video_db")
MIN_SCORE     = float(os.environ.get("ASSET_DB_MIN_SCORE", "0.72"))


@dataclass
class AssetResult:
    id:           int
    file_path:    str
    source:       str
    keywords:     list[str]
    niche:        list[str]
    duration_s:   float
    resolution:   str
    aspect_ratio: str
    quality_score: float
    match_score:  float


def search(
    keywords:     list[str],
    niche:        str,
    min_duration: float,
    aspect_ratio: str = "9:16",
    min_score:    float | None = None,
) -> AssetResult | None:
    """
    Find the best matching asset in the DB.
    Uses keyword overlap scoring; returns None if no match above threshold.
    """
    from database.connection import get_session
    from database.models import VideoAsset
    from sqlalchemy import text

    threshold = min_score if min_score is not None else MIN_SCORE
    db = get_session()
    try:
        # Raw SQL for array intersection scoring
        sql = text("""
            SELECT
                id, file_path, source, keywords, niche, duration_s,
                resolution, aspect_ratio, quality_score,
                (
                    COALESCE(
                        array_length(
                            ARRAY(
                                SELECT unnest(keywords)
                                INTERSECT
                                SELECT unnest(:kw_array)
                            ),
                            1
                        ), 0
                    )::float / GREATEST(array_length(keywords, 1), 1)
                ) AS match_score
            FROM video_assets
            WHERE duration_s >= :min_duration
              AND aspect_ratio = :aspect_ratio
                            AND (:niche = '' OR niche::text[] @> ARRAY[:niche]::text[])
              AND (expires_at IS NULL OR expires_at > NOW())
            ORDER BY match_score DESC, usage_count ASC, quality_score DESC
            LIMIT 5
        """)

        rows = db.execute(sql, {
            "kw_array":    keywords,
            "min_duration": min_duration,
            "aspect_ratio": aspect_ratio,
            "niche":        niche,
        }).fetchall()

        if not rows:
            return None

        best = rows[0]
        score = float(best.match_score or 0)
        if score < threshold:
            return None

        # Update usage count
        db.execute(
            text("UPDATE video_assets SET usage_count = usage_count + 1, last_used_at = NOW() WHERE id = :id"),
            {"id": best.id},
        )
        db.commit()

        return AssetResult(
            id=best.id,
            file_path=best.file_path,
            source=best.source,
            keywords=best.keywords or [],
            niche=best.niche or [],
            duration_s=best.duration_s,
            resolution=best.resolution or "",
            aspect_ratio=best.aspect_ratio or "9:16",
            quality_score=float(best.quality_score or 0),
            match_score=score,
        )
    finally:
        db.close()


def write(
    file_path:     str,
    source:        str,
    keywords:      list[str],
    niche:         str,
    quality_score: float = 0.8,
    veo_prompt:    str | None = None,
    source_id:     str | None = None,
) -> int:
    """
    Ingest a new clip into the Asset DB.
    Probes the file with ffprobe for metadata. Returns new asset ID.
    """
    from database.connection import get_session
    from database.models import VideoAsset

    meta = _probe_video(file_path)
    file_hash = _sha256(file_path)

    db = get_session()
    try:
        # Check for duplicate by hash
        existing = db.query(VideoAsset).filter(VideoAsset.file_hash == file_hash).first()
        if existing:
            logger.debug(f"[AssetDB] Duplicate file hash {file_hash[:8]}, skipping insert")
            return existing.id

        asset = VideoAsset(
            file_path=file_path,
            file_hash=file_hash,
            source=source,
            source_id=source_id,
            veo_prompt=veo_prompt,
            keywords=keywords,
            niche=[niche] if isinstance(niche, str) else niche,
            duration_s=meta.get("duration", 0.0),
            resolution=meta.get("resolution", ""),
            aspect_ratio=meta.get("aspect_ratio", "9:16"),
            fps=meta.get("fps", 30),
            file_size_mb=meta.get("size_mb", 0.0),
            quality_score=quality_score,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        logger.info(f"[AssetDB] Wrote asset {asset.id} — {source} {file_path}")
        return asset.id
    finally:
        db.close()


def _probe_video(file_path: str) -> dict:
    """Extract duration, resolution, fps, file size using ffprobe."""
    try:
        import json as _json
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", file_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = _json.loads(result.stdout)

        video_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
            {},
        )
        duration = float(data.get("format", {}).get("duration", 0))
        width    = int(video_stream.get("width", 0))
        height   = int(video_stream.get("height", 0))
        fps_str  = video_stream.get("r_frame_rate", "30/1")
        try:
            num, den = fps_str.split("/")
            fps = int(int(num) / int(den))
        except Exception:
            fps = 30

        size_mb      = os.path.getsize(file_path) / 1024 / 1024
        resolution   = f"{width}x{height}" if width and height else ""
        aspect_ratio = "9:16" if height > width else "16:9"

        return {
            "duration": duration, "resolution": resolution,
            "aspect_ratio": aspect_ratio, "fps": fps, "size_mb": round(size_mb, 2),
        }
    except Exception as e:
        logger.warning(f"[AssetDB] ffprobe failed for {file_path}: {e}")
        size_mb = os.path.getsize(file_path) / 1024 / 1024 if os.path.exists(file_path) else 0
        return {"duration": 0.0, "resolution": "", "aspect_ratio": "9:16", "fps": 30, "size_mb": size_mb}


def _sha256(file_path: str) -> str:
    sha = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
    except Exception:
        pass
    return sha.hexdigest()
