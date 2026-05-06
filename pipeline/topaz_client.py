import json
import subprocess
from pathlib import Path

import requests


class TopazClient:
    BASE = "https://api.topazlabs.com"

    def __init__(self, api_key: str):
        self._api_key = api_key

    def _headers(self) -> dict:
        return {"X-API-Key": self._api_key, "accept": "application/json"}

    def create_job(self, width: int, height: int, fps: int, duration: float, size: int) -> str:
        """Create a Topaz upscale job. Returns request_id."""
        payload = {
            "source": {
                "container": "mp4",
                "size": size,
                "duration": duration,
                "frameRate": fps,
                "frameCount": 0,
                "resolution": {"width": width, "height": height},
            },
            "filters": [{
                "model": "ast-2",
                "creativity": 0.6,
                "prompt": "cinematic, detailed, natural texture",
                "sharp": 0.5,
                "realism": 0.5,
                "input_frame_rate": fps,
                "input_width": width,
                "input_height": height,
                "output_width": width * 2,
                "output_height": height * 2,
            }],
            "output": {
                "resolution": {"width": width * 2, "height": height * 2},
                "frameRate": fps,
                "audioCodec": "AAC",
                "audioTransfer": "Copy",
                "videoEncoder": "H265",
                "dynamicCompressionLevel": "High",
                "container": "mp4",
            },
        }
        resp = requests.post(
            f"{self.BASE}/video/",
            headers={**self._headers(), "content-type": "application/json"},
            data=json.dumps(payload),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["requestId"]

    def accept_job(self, request_id: str) -> str:
        """Accept the job and get the presigned upload URL."""
        resp = requests.patch(f"{self.BASE}/video/{request_id}/accept", headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()["urls"][0]

    def upload_file(self, upload_url: str, file_path: Path) -> str:
        """Upload the source file. Returns ETag."""
        with open(file_path, "rb") as f:
            resp = requests.put(upload_url, data=f, headers={"Content-Type": "video/mp4"}, timeout=300)
        resp.raise_for_status()
        return resp.headers["ETag"]

    def complete_upload(self, request_id: str, etag: str) -> None:
        """Signal that the multipart upload is complete."""
        resp = requests.patch(
            f"{self.BASE}/video/{request_id}/complete-upload",
            headers={**self._headers(), "content-type": "application/json"},
            json={"uploadResults": [{"partNum": 1, "eTag": etag}]},
            timeout=30,
        )
        resp.raise_for_status()

    def get_status(self, request_id: str) -> dict:
        """Poll job status. Returns dict with 'status' and optional 'download.url'."""
        resp = requests.get(f"{self.BASE}/video/{request_id}/status", headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()

    def download_result(self, download_url: str, dest_path: Path) -> None:
        """Stream-download the 4K result to dest_path."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(download_url, stream=True, timeout=300) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

    def test_connection(self) -> dict:
        """Verify the API key. 401 = invalid key, anything else = key authenticated."""
        try:
            resp = requests.get(f"{self.BASE}/video/", headers=self._headers(), timeout=10)
            if resp.status_code == 401:
                return {"connected": False, "message": "Invalid API key"}
            return {"connected": True, "message": "Connected to Topaz API"}
        except requests.RequestException as exc:
            return {"connected": False, "message": str(exc)}


def probe_video_metadata(file_path: Path) -> dict:
    """Extract width, height, fps, duration, size via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", str(file_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    video_stream = next(s for s in data["streams"] if s["codec_type"] == "video")
    fps_str = video_stream.get("r_frame_rate", "30/1")
    num, den = map(int, fps_str.split("/"))
    fps = round(num / den)
    return {
        "width": int(video_stream["width"]),
        "height": int(video_stream["height"]),
        "fps": fps,
        "duration": float(data["format"].get("duration", 0)),
        "size": int(data["format"].get("size", 0)),
    }
