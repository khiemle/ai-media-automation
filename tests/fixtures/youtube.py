"""Canned YouTube Data API v3 responses."""
from __future__ import annotations


def video_resource(video_id: str = "abc123", title: str = "Test Video") -> dict:
    """Shape returned by youtube.videos().insert() and .list()."""
    return {
        "kind": "youtube#video",
        "id": video_id,
        "snippet": {
            "title": title,
            "description": "test description",
            "tags": ["test"],
            "categoryId": "22",
        },
        "status": {"privacyStatus": "private", "uploadStatus": "uploaded"},
        "statistics": {"viewCount": "0", "likeCount": "0"},
    }


def upload_progress(percent: int = 100) -> dict:
    """Shape used internally by the resumable uploader's status callback."""
    return {"progress": percent / 100.0, "resumable_progress": percent, "total_size": 100}
