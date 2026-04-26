"""Suno API client — submit generation tasks and poll for results."""
import os
import requests


SUNO_BASE = "https://api.sunoapi.org/api/v1"
SUNO_MODEL = "V4_5"


class SunoProvider:
    def __init__(self):
        self._key = os.environ.get("SUNO_API_KEY", "")
        if not self._key:
            raise RuntimeError("SUNO_API_KEY is not set")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}

    def submit(
        self,
        prompt: str,
        style: str,
        title: str,
        instrumental: bool = True,
        negative_tags: str = "",
    ) -> str:
        """Submit a generation request. Returns Suno taskId."""
        payload = {
            "customMode": True,
            "model": SUNO_MODEL,
            "instrumental": instrumental,
            "prompt": prompt,
            "style": style,
            "title": title,
            "callBackUrl": "https://placeholder.invalid/noop",
        }
        if negative_tags:
            payload["negativeTags"] = negative_tags

        resp = requests.post(f"{SUNO_BASE}/generate", json=payload, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["data"]["taskId"]

    def poll(self, task_id: str) -> str | None:
        """
        Poll for task completion.
        Returns the first audio URL on SUCCESS, None if still pending, raises on failure.
        """
        resp = requests.get(
            f"{SUNO_BASE}/generate/record-info",
            params={"taskId": task_id},
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        status = data.get("status", "")
        if status == "SUCCESS":
            suno_data = data.get("sunoData", [])
            if suno_data:
                return suno_data[0].get("audioUrl")
        if status == "FAILED":
            raise RuntimeError(f"Suno generation failed for task {task_id}")
        return None  # still pending
