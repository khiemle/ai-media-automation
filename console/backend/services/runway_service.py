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
