"""Tests for suggestguard.collectors module (mocked httpx, no real requests)."""

from __future__ import annotations

import json

import httpx
import pytest

from suggestguard.collectors.autocomplete import AutocompleteCollector

# ── helpers ──────────────────────────────────────────────────────────


def _mock_response(data: list, status: int = 200) -> httpx.Response:
    """Build a fake httpx.Response with JSON body."""
    return httpx.Response(
        status_code=status,
        json=data,
        request=httpx.Request("GET", "https://example.com"),
    )


class MockTransport(httpx.AsyncBaseTransport):
    """Custom transport that returns canned responses without hitting the network."""

    def __init__(self, handler):
        self._handler = handler

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return self._handler(request)


def _make_client(handler) -> httpx.AsyncClient:
    """Create an AsyncClient wired to *handler* (no real I/O)."""
    return httpx.AsyncClient(transport=MockTransport(handler))


# ── collect (single query) ───────────────────────────────────────────


class TestCollect:
    @pytest.mark.asyncio
    async def test_successful_response(self):
        def handler(request: httpx.Request):
            return _mock_response(["marka", ["marka şikayet", "marka yorumlar"]])

        client = _make_client(handler)
        collector = AutocompleteCollector(request_delay=0, client=client)

        results = await collector.collect("marka")
        assert results == ["marka şikayet", "marka yorumlar"]
        await client.aclose()

    @pytest.mark.asyncio
    async def test_empty_suggestions(self):
        def handler(request: httpx.Request):
            return _mock_response(["marka", []])

        client = _make_client(handler)
        collector = AutocompleteCollector(request_delay=0, client=client)

        results = await collector.collect("marka")
        assert results == []
        await client.aclose()

    @pytest.mark.asyncio
    async def test_malformed_response(self):
        def handler(request: httpx.Request):
            return _mock_response(["only_one_element"])

        client = _make_client(handler)
        collector = AutocompleteCollector(request_delay=0, client=client)

        results = await collector.collect("marka")
        assert results == []
        await client.aclose()

    @pytest.mark.asyncio
    async def test_query_params_sent(self):
        captured = {}

        def handler(request: httpx.Request):
            captured["url"] = str(request.url)
            return _mock_response(["q", ["s1"]])

        client = _make_client(handler)
        collector = AutocompleteCollector(request_delay=0, client=client)

        await collector.collect("test query", language="en", country="US")
        assert "hl=en" in captured["url"]
        assert "gl=US" in captured["url"]
        assert "client=firefox" in captured["url"]
        assert "test+query" in captured["url"] or "test%20query" in captured["url"]
        await client.aclose()

    @pytest.mark.asyncio
    async def test_http_429_raises(self):
        def handler(request: httpx.Request):
            return _mock_response([], status=429)

        client = _make_client(handler)
        collector = AutocompleteCollector(request_delay=0, client=client)

        with pytest.raises(httpx.HTTPStatusError):
            await collector.collect("marka")
        await client.aclose()

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        async def handler(request: httpx.Request):
            raise httpx.ReadTimeout("timed out")

        # Use a transport that raises inside handle_async_request
        class TimeoutTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                raise httpx.ReadTimeout("timed out")

        client = httpx.AsyncClient(transport=TimeoutTransport())
        collector = AutocompleteCollector(request_delay=0, client=client)

        with pytest.raises(httpx.TimeoutException):
            await collector.collect("marka")
        await client.aclose()


# ── collect_brand ────────────────────────────────────────────────────


class TestCollectBrand:
    @pytest.mark.asyncio
    async def test_collects_all_variants(self):
        def handler(request: httpx.Request):
            q = str(request.url.params.get("q", ""))
            return _mock_response([q, [f"{q} suggestion"]])

        client = _make_client(handler)
        collector = AutocompleteCollector(request_delay=0, max_workers=5, client=client)

        brand = {
            "keywords": json.dumps(["marka"]),
            "language": "tr",
            "country": "TR",
            "expand_az": False,
            "expand_turkish": False,
        }

        results = await collector.collect_brand(brand)
        assert len(results) == 1  # only base query, no expansion
        assert results[0]["query"] == "marka"
        assert results[0]["suggestions"] == ["marka suggestion"]
        assert results[0]["source"] == "autocomplete"
        assert "timestamp" in results[0]
        await client.aclose()

    @pytest.mark.asyncio
    async def test_expand_az_generates_queries(self):
        def handler(request: httpx.Request):
            return _mock_response(["q", []])

        client = _make_client(handler)
        collector = AutocompleteCollector(request_delay=0, max_workers=10, client=client)

        brand = {
            "keywords": json.dumps(["test"]),
            "language": "tr",
            "country": "TR",
            "expand_az": True,
            "expand_turkish": False,
        }

        results = await collector.collect_brand(brand)
        # base(1) + 26 a-z = 27
        assert len(results) == 27
        await client.aclose()

    @pytest.mark.asyncio
    async def test_multiple_keywords_deduplicated(self):
        call_count = 0

        def handler(request: httpx.Request):
            nonlocal call_count
            call_count += 1
            return _mock_response(["q", []])

        client = _make_client(handler)
        collector = AutocompleteCollector(request_delay=0, max_workers=10, client=client)

        brand = {
            "keywords": json.dumps(["same", "same"]),  # duplicate keywords
            "language": "tr",
            "country": "TR",
            "expand_az": False,
            "expand_turkish": False,
        }

        results = await collector.collect_brand(brand)
        # duplicates removed → only 1 query
        assert len(results) == 1
        assert call_count == 1
        await client.aclose()

    @pytest.mark.asyncio
    async def test_keywords_as_list(self):
        """brand['keywords'] can be a plain list (not JSON string)."""

        def handler(request: httpx.Request):
            return _mock_response(["q", []])

        client = _make_client(handler)
        collector = AutocompleteCollector(request_delay=0, client=client)

        brand = {
            "keywords": ["marka"],
            "language": "tr",
            "country": "TR",
            "expand_az": False,
            "expand_turkish": False,
        }

        results = await collector.collect_brand(brand)
        assert len(results) == 1
        await client.aclose()

    @pytest.mark.asyncio
    async def test_progress_callback(self):
        def handler(request: httpx.Request):
            return _mock_response(["q", []])

        client = _make_client(handler)
        collector = AutocompleteCollector(request_delay=0, max_workers=1, client=client)

        progress_log: list[tuple[int, int, str]] = []

        def on_progress(current: int, total: int, query: str):
            progress_log.append((current, total, query))

        brand = {
            "keywords": json.dumps(["x"]),
            "language": "tr",
            "country": "TR",
            "expand_az": False,
            "expand_turkish": False,
        }

        await collector.collect_brand(brand, progress_callback=on_progress)
        assert len(progress_log) == 1
        current, total, query = progress_log[0]
        assert current == 1
        assert total == 1
        assert query == "x"
        await client.aclose()

    @pytest.mark.asyncio
    async def test_http_error_captured_in_results(self):
        """429 / 5xx errors should NOT crash collect_brand; they appear as error entries."""

        def handler(request: httpx.Request):
            return _mock_response([], status=429)

        client = _make_client(handler)
        collector = AutocompleteCollector(request_delay=0, client=client)

        brand = {
            "keywords": json.dumps(["bad"]),
            "language": "tr",
            "country": "TR",
            "expand_az": False,
            "expand_turkish": False,
        }

        results = await collector.collect_brand(brand)
        assert len(results) == 1
        assert results[0]["suggestions"] == []
        assert "error" in results[0]
        assert "429" in results[0]["error"]
        await client.aclose()

    @pytest.mark.asyncio
    async def test_timeout_captured_in_results(self):
        class TimeoutTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                raise httpx.ReadTimeout("timed out")

        client = httpx.AsyncClient(transport=TimeoutTransport())
        collector = AutocompleteCollector(request_delay=0, client=client)

        brand = {
            "keywords": json.dumps(["slow"]),
            "language": "tr",
            "country": "TR",
            "expand_az": False,
            "expand_turkish": False,
        }

        results = await collector.collect_brand(brand)
        assert len(results) == 1
        assert results[0]["suggestions"] == []
        assert "error" in results[0]
        assert "ReadTimeout" in results[0]["error"]
        await client.aclose()


# ── lifecycle ────────────────────────────────────────────────────────


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_close_internal_client(self):
        collector = AutocompleteCollector(request_delay=0)
        # Force client creation
        client = await collector._get_client()
        assert client is not None
        await collector.close()
        assert collector._client is None

    @pytest.mark.asyncio
    async def test_close_does_not_close_external_client(self):
        client = httpx.AsyncClient()
        collector = AutocompleteCollector(request_delay=0, client=client)
        await collector.close()
        # External client should NOT be closed by collector
        assert collector._client is client
        await client.aclose()
