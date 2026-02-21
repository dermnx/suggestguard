"""Generic webhook notification sender."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class WebhookNotifier:
    """POST JSON payloads to an arbitrary webhook endpoint."""

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.url = url
        self.headers = headers or {}
        self._external_client = client is not None
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._external_client:
            await self._client.aclose()
            self._client = None

    async def send(self, payload: dict) -> bool:
        """POST *payload* as JSON. Returns True on success."""
        client = await self._get_client()
        try:
            resp = await client.post(self.url, json=payload, headers=self.headers)
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("Webhook HTTP %s: %s", exc.response.status_code, exc.response.text)
            return False
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.error("Webhook connection error: %s", exc)
            return False
