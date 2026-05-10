"""
YouTube Data API v3 uploader.
Uses OAuth credentials stored (Fernet-encrypted) in the console DB.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
except ImportError:
    build = None  # type: ignore[assignment]
    MediaFileUpload = None  # type: ignore[assignment]
    Credentials = None  # type: ignore[assignment]
    Request = None  # type: ignore[assignment]

CHUNK_SIZE = 10 * 1024 * 1024   # 10MB resumable upload chunks


def upload(
    video_path:  str | Path,
    metadata:    dict,
    credentials: dict,
    chapters:    list[dict] | None = None,
) -> str:
    """
    Upload a video to YouTube using the Data API v3.

    Args:
        video_path:  Path to video_final.mp4
        metadata:    dict with keys: title, description, hashtags, niche, template,
                     language (default "en"), privacy_status (default "unlisted")
        credentials: dict with keys: client_id, client_secret, access_token, refresh_token

    Returns: YouTube video ID (e.g. 'dQw4w9WgXcQ')
    """
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        raise RuntimeError(
            "google-api-python-client not installed. "
            "Run: pip install google-api-python-client google-auth"
        )

    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    creds = Credentials(
        token=credentials.get("access_token"),
        refresh_token=credentials.get("refresh_token"),
        client_id=credentials.get("client_id"),
        client_secret=credentials.get("client_secret"),
        token_uri="https://oauth2.googleapis.com/token",
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        logger.info("[YouTube] Token refreshed")

    youtube = build("youtube", "v3", credentials=creds)

    title          = metadata.get("title", video_path.stem)[:100]
    description    = _build_description(metadata, chapters=chapters)
    tags           = _build_tags(metadata)
    category_id    = _niche_to_category(metadata.get("niche", "lifestyle"))
    language       = metadata.get("language", "en")
    privacy_status = metadata.get("privacy_status", "unlisted")

    body = {
        "snippet": {
            "title":           title,
            "description":     description,
            "tags":            tags,
            "categoryId":      category_id,
            "defaultLanguage": language,
        },
        "status": {
            "privacyStatus":           privacy_status,
            "selfDeclaredMadeForKids": False,
            "selfDeclaration": {
                "hasSyntheticOrAltered": True,
            },
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=CHUNK_SIZE,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            logger.info(f"[YouTube] Upload progress: {progress}%")

    video_id = response.get("id", "")
    logger.info(f"[YouTube] Uploaded: https://youtube.com/watch?v={video_id}")
    return video_id


def _fmt_timestamp(seconds: int) -> str:
    """Format as M:SS or H:MM:SS depending on duration."""
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _format_chapters(chapters: list[dict]) -> str:
    """Format chapter list as YouTube-compatible timestamp lines.

    First chapter is FORCED to 0:00 per YouTube's spec, even if the
    input boundary is non-zero (defensive guard for off-by-one bugs).
    """
    lines = []
    for i, ch in enumerate(chapters):
        ts = 0 if i == 0 else int(ch["seconds"])
        lines.append(f"{_fmt_timestamp(ts)} {ch['title']}")
    return "\n".join(lines)


def build_description_with_chapters(
    body: str,
    chapters: list[dict] | None,
    hashtags: list[str] | None = None,
) -> str:
    """Compose the final YouTube description.

    When chapters has >= 3 entries, prepends a chapters block with a
    blank-line separator. Otherwise returns body unchanged (plus optional
    hashtag block).
    """
    parts = []
    if chapters and len(chapters) >= 3:
        parts.append(_format_chapters(chapters))
        parts.append("")
    parts.append(body)
    if hashtags:
        parts.append("")
        parts.append(" ".join(f"#{h.lstrip('#')}" for h in hashtags))
    return "\n".join(parts)


def _build_description(metadata: dict, chapters: list[dict] | None = None) -> str:
    desc      = metadata.get("description", "")
    hashtags  = metadata.get("hashtags", [])
    affiliate = metadata.get("affiliate_links", [])

    # Build the body portion (description + affiliate links)
    body_parts = [desc]
    if affiliate:
        body_parts.append("\n🔗 Links:\n" + "\n".join(affiliate))
    body = "\n\n".join(p for p in body_parts if p).strip()

    # Build hashtag line — always include #Shorts
    ht_tags = [f"#{h.lstrip('#')}" for h in hashtags[:14]]
    if "#Shorts" not in ht_tags:
        ht_tags.append("#Shorts")
    ht_line = " ".join(ht_tags)

    # Use chapters helper to compose full description
    result = build_description_with_chapters(
        body=body,
        chapters=chapters,
        hashtags=[ht_line] if ht_line else None,
    )
    return result[:5000]


def _build_tags(metadata: dict) -> list[str]:
    # Shorts must be first so YouTube reliably classifies the video
    tags = ["Shorts"]
    for h in metadata.get("hashtags", []):
        tag = h.lstrip("#")
        if tag != "Shorts":
            tags.append(tag)
    niche = metadata.get("niche", "")
    if niche and niche not in tags:
        tags.append(niche)
    return tags[:500]


def _niche_to_category(niche: str) -> str:
    mapping = {
        "health":       "26",   # Howto & Style
        "fitness":      "17",   # Sports
        "running":      "17",   # Sports
        "lifestyle":    "26",   # Howto & Style
        "finance":      "27",   # Education
        "food":         "26",   # Howto & Style
        "productivity": "27",   # Education
    }
    return mapping.get(niche, "22")   # 22 = People & Blogs


# Legacy alias used by console upload task
def upload_to_youtube(video_path, metadata, credentials) -> str:
    return upload(video_path, metadata, credentials)


def set_thumbnail(platform_video_id: str, thumbnail_path: str | Path, credentials: dict) -> None:
    """Set a custom thumbnail on a YouTube video via the Data API v3.

    Logs a warning on API failure and returns silently; does not raise on API error.
    Raises FileNotFoundError if thumbnail_path does not exist on disk.
    """
    thumbnail_path = Path(thumbnail_path)
    if not thumbnail_path.exists():
        raise FileNotFoundError(f"Thumbnail file not found: {thumbnail_path}")

    if build is None:
        raise RuntimeError(
            "google-api-python-client not installed. "
            "Run: pip install google-api-python-client google-auth"
        )

    creds = Credentials(
        token=credentials.get("access_token"),
        refresh_token=credentials.get("refresh_token"),
        client_id=credentials.get("client_id"),
        client_secret=credentials.get("client_secret"),
        token_uri="https://oauth2.googleapis.com/token",
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        logger.info("[YouTube] Token refreshed for thumbnail set")

    youtube = build("youtube", "v3", credentials=creds)
    media = MediaFileUpload(str(thumbnail_path), mimetype="image/png")
    try:
        youtube.thumbnails().set(videoId=platform_video_id, media_body=media).execute()
        logger.info("[YouTube] Thumbnail set for video %s", platform_video_id)
    except Exception as exc:
        logger.warning("[YouTube] Thumbnail set failed for video %s: %s", platform_video_id, exc)
