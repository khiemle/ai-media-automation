"""Thin httpx wrapper that talks to the existing console FastAPI."""
from __future__ import annotations

import json as _json
from typing import Any, Callable

import httpx

from console.mcp.errors import ConsoleError, map_http_error

TokenProvider = Callable[[], str]


class ConsoleClient:
    def __init__(
        self,
        *,
        base_url: str,
        token_provider: TokenProvider,
        actor_metadata: dict[str, Any] | None = None,
        on_unauthorized: Callable[[], None] | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._token = token_provider
        self._actor = actor_metadata or {}
        self._on_unauthorized = on_unauthorized
        self._client = httpx.AsyncClient(timeout=timeout)

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        return await self._request("POST", path, json=json)

    async def put(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        return await self._request("PUT", path, json=json)

    async def patch(self, path: str, *, json: dict[str, Any] | None = None) -> Any:
        return await self._request("PATCH", path, json=json)

    async def delete(self, path: str) -> Any:
        return await self._request("DELETE", path)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,  # noqa: A002
    ) -> Any:
        url = f"{self._base}{path}"
        resp = await self._do(method, url, params=params, json_body=json)
        if resp.status_code == 401 and self._on_unauthorized is not None:
            self._on_unauthorized()
            resp = await self._do(method, url, params=params, json_body=json)
        if resp.status_code >= 400:
            raise map_http_error(resp)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    async def _do(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None,
        json_body: dict[str, Any] | None,
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._token()}"}
        if self._actor:
            headers["X-Mcp-Actor-Metadata"] = _json.dumps(self._actor, separators=(",", ":"))
        content: bytes | None = None
        if json_body is not None:
            content = _json.dumps(json_body).encode()
            headers["Content-Type"] = "application/json"
        return await self._client.request(method, url, params=params, content=content, headers=headers)

    async def aclose(self) -> None:
        await self._client.aclose()
