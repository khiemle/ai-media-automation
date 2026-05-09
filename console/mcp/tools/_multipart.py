"""Multipart upload helper for MCP tools.

Reads a local file from disk and returns it in the format httpx expects for
multipart/form-data uploads.

NOTE: The entire file is read into memory before sending. This is fine for
small uploads (SFX .wav, thumbnail .png, channel-plan .md). For large visual
assets (multi-GB .mp4) this could exhaust memory. See FOLLOWUPS.md —
"Streaming for large uploads".
"""
import mimetypes
import os


def open_for_upload(file_path: str, *, field: str = "file") -> dict:
    """Read a local file into the format httpx expects for multipart.

    Returns a ``files=`` kwarg dict ready to pass to
    ``ConsoleClient.multipart_post``.

    Raises ``FileNotFoundError`` if the path does not exist or is not a file.
    The caller is responsible for surfacing this as a validation error to the
    agent.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"file not found: {file_path}")
    filename = os.path.basename(file_path)
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    with open(file_path, "rb") as f:
        data = f.read()
    return {field: (filename, data, content_type)}
