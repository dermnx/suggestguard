"""Google Autocomplete suggestion collector."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable

import httpx

from suggestguard.analyzers.turkish import TurkishTextProcessor
from suggestguard.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

AUTOCOMPLETE_URL = "https://www.google.com/complete/search"


class AutocompleteCollector(BaseCollector):
    """Fetches suggestions from the Google Autocomplete API."""

    def __init__(
        self,
        request_delay: float = 1.5,
        max_workers: int = 3,
        user_agent: str = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.request_delay = request_delay
        self.max_workers = max_workers
        self.user_agent = user_agent
        self._external_client = client is not None
        self._client = client
        self._tp = TurkishTextProcessor()

    # ── lifecycle ────────────────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": self.user_agent},
                timeout=10.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._external_client:
            await self._client.aclose()
            self._client = None

    # ── single query ─────────────────────────────────────────────────

    async def collect(
        self,
        query: str,
        language: str = "tr",
        country: str = "TR",
    ) -> list[str]:
        """Fetch autocomplete suggestions for a single query."""
        client = await self._get_client()
        params = {
            "client": "firefox",
            "hl": language,
            "gl": country,
            "q": query,
        }
        resp = await client.get(AUTOCOMPLETE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        # Firefox-style response: [query, [suggestions...]]
        if isinstance(data, list) and len(data) >= 2:
            return list(data[1])
        return []

    # ── full brand scan ──────────────────────────────────────────────

    async def collect_brand(
        self,
        brand: dict,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> list[dict]:
        """Collect suggestions for every query variant of *brand*."""
        keywords: list[str] = (
            json.loads(brand["keywords"])
            if isinstance(brand["keywords"], str)
            else brand["keywords"]
        )
        language = brand.get("language", "tr")
        country = brand.get("country", "TR")
        expand_az = bool(brand.get("expand_az", True))
        expand_turkish = bool(brand.get("expand_turkish", True))

        queries: list[str] = []
        for kw in keywords:
            queries.extend(
                self._tp.generate_query_variants(
                    kw, expand_az=expand_az, expand_turkish=expand_turkish
                )
            )
        # deduplicate while preserving order
        seen: set[str] = set()
        unique_queries: list[str] = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                unique_queries.append(q)

        total = len(unique_queries)
        results: list[dict] = []
        sem = asyncio.Semaphore(self.max_workers)
        counter = 0
        lock = asyncio.Lock()

        async def _fetch(query: str) -> dict | None:
            nonlocal counter
            async with sem:
                try:
                    suggestions = await self.collect(query, language, country)
                    result = {
                        "query": query,
                        "suggestions": suggestions,
                        "source": "autocomplete",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                except httpx.HTTPStatusError as exc:
                    logger.warning("HTTP %s for query %r", exc.response.status_code, query)
                    result = {
                        "query": query,
                        "suggestions": [],
                        "source": "autocomplete",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "error": f"HTTP {exc.response.status_code}",
                    }
                except (httpx.TimeoutException, httpx.ConnectError) as exc:
                    logger.warning("Timeout/connect error for query %r: %s", query, exc)
                    result = {
                        "query": query,
                        "suggestions": [],
                        "source": "autocomplete",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "error": type(exc).__name__,
                    }

                async with lock:
                    counter += 1
                    if progress_callback is not None:
                        progress_callback(counter, total, query)

                if self.request_delay > 0:
                    await asyncio.sleep(self.request_delay)

                return result

        tasks = [_fetch(q) for q in unique_queries]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            if result is not None:
                results.append(result)

        return results
