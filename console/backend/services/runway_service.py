"""Runway Workflow API client — submit and poll workflow invocations."""
import os
from typing import Any

import requests

RUNWAY_API_BASE = "https://api.dev.runwayml.com/v1"
RUNWAY_VERSION = "2024-11-06"


class RunwayService:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("RUNWAY_API_KEY", "")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": RUNWAY_VERSION,
        }

    def submit_workflow(
        self,
        workflow_id: str,
        prompt_node_id: str,
        image_node_id: str,
        prompt: str,
        image_uri: str,
    ) -> str:
        """POST /workflows/{workflow_id} → returns invocation_id."""
        body = {
            "nodeOutputs": {
                prompt_node_id: {
                    "prompt": {"type": "primitive", "value": prompt}
                },
                image_node_id: {
                    "image": {"type": "image", "uri": image_uri}
                },
            }
        }
        resp = requests.post(
            f"{RUNWAY_API_BASE}/workflows/{workflow_id}",
            json=body,
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def poll_workflow_invocation(self, invocation_id: str) -> dict[str, Any]:
        """GET /workflow_invocations/{invocation_id}
        Returns {"status": "PENDING|RUNNING|SUCCEEDED|FAILED", "output_url": str|None}

        The exact output field varies by Runway API version. We try `outputs`
        (list of dicts with "url") then `output` (list of strings) as a fallback.
        Log the raw response if neither matches on SUCCEEDED to aid debugging.
        """
        resp = requests.get(
            f"{RUNWAY_API_BASE}/workflow_invocations/{invocation_id}",
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "PENDING")

        output_url = None
        if status == "SUCCEEDED":
            outputs = data.get("outputs")
            if isinstance(outputs, list) and outputs:
                first = outputs[0]
                output_url = first.get("url") if isinstance(first, dict) else first
            if output_url is None:
                fallback = data.get("output")
                if isinstance(fallback, list) and fallback:
                    output_url = fallback[0]
                elif isinstance(fallback, str):
                    output_url = fallback
            if output_url is None:
                import logging
                logging.getLogger(__name__).warning(
                    "SUCCEEDED invocation %s has no recognised output field. Raw: %s",
                    invocation_id, data,
                )

        return {"status": status, "output_url": output_url}

    def test_connection(self) -> dict:
        """Probe the dev API. 404 = auth OK, 401/403 = bad key."""
        try:
            resp = requests.get(
                f"{RUNWAY_API_BASE}/workflow_invocations/ping",
                headers=self._headers(),
                timeout=10,
            )
            if resp.status_code in (200, 404):
                return {"ok": True, "error": None}
            if resp.status_code in (401, 403):
                return {"ok": False, "error": f"Invalid API key (HTTP {resp.status_code})"}
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
