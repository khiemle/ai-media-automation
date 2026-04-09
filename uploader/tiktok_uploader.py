"""
TikTok Content Posting API v2 uploader.
Uses OAuth credentials stored in the console DB.
"""
import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

TIKTOK_UPLOAD_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
TIKTOK_STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
CHUNK_SIZE = 10 * 1024 * 1024   # 10MB


def upload(
    video_path:  str | Path,
    metadata:    dict,
    credentials: dict,
) -> str:
    """
    Upload a video to TikTok using the Content Posting API v2.

    Args:
        video_path:  Path to video_final.mp4
        metadata:    dict with keys: title, hashtags, niche
        credentials: dict with keys: access_token

    Returns: TikTok publish_id
    """
    video_path   = Path(video_path)
    access_token = credentials.get("access_token", "")

    if not access_token:
        raise ValueError("TikTok access_token is required")
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type":  "application/json",
    }

    caption = _build_caption(metadata)
    file_size = video_path.stat().st_size

    # Step 1: Initialize upload
    init_body = {
        "post_info": {
            "title":          caption[:2200],
            "privacy_level":  "PUBLIC_TO_EVERYONE",
            "disable_duet":   False,
            "disable_stitch": False,
            "disable_comment": False,
            "video_cover_timestamp_ms": 1000,
        },
        "source_info": {
            "source":          "FILE_UPLOAD",
            "video_size":      file_size,
            "chunk_size":      CHUNK_SIZE,
            "total_chunk_count": _chunk_count(file_size),
        },
    }

    resp = httpx.post(TIKTOK_UPLOAD_URL, json=init_body, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json().get("data", {})

    publish_id  = data.get("publish_id", "")
    upload_url  = data.get("upload_url", "")

    if not publish_id or not upload_url:
        raise RuntimeError(f"TikTok upload init failed: {resp.text[:300]}")

    # Step 2: Upload file chunks
    _upload_chunks(video_path, upload_url, file_size)

    logger.info(f"[TikTok] Upload complete — publish_id: {publish_id}")
    return publish_id


def _upload_chunks(video_path: Path, upload_url: str, file_size: int):
    """Upload video file in chunks to TikTok's upload URL."""
    chunk_index = 0
    offset      = 0

    with open(video_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break

            end = min(offset + len(chunk) - 1, file_size - 1)
            headers = {
                "Content-Type":  "video/mp4",
                "Content-Range": f"bytes {offset}-{end}/{file_size}",
                "Content-Length": str(len(chunk)),
            }

            resp = httpx.put(upload_url, content=chunk, headers=headers, timeout=120)
            if resp.status_code not in (200, 201, 206):
                raise RuntimeError(f"TikTok chunk {chunk_index} upload failed: {resp.status_code}")

            logger.debug(f"[TikTok] Chunk {chunk_index} uploaded ({offset}-{end})")
            offset      += len(chunk)
            chunk_index += 1


def _chunk_count(file_size: int) -> int:
    import math
    return max(1, math.ceil(file_size / CHUNK_SIZE))


def _build_caption(metadata: dict) -> str:
    title    = metadata.get("title", "")
    hashtags = metadata.get("hashtags", [])
    tag_str  = " ".join(f"#{h.lstrip('#')}" for h in hashtags[:30])
    return f"{title}\n{tag_str}".strip()[:2200]


# Legacy alias used by console upload task
def upload_to_tiktok(video_path, metadata, credentials) -> str:
    return upload(video_path, metadata, credentials)
