"""Tests for suggestguard.notifiers (mocked httpx, no real requests)."""

from __future__ import annotations

import json

import httpx
import pytest

from suggestguard.notifiers import get_notifiers
from suggestguard.notifiers.slack import SlackNotifier
from suggestguard.notifiers.telegram import TelegramNotifier
from suggestguard.notifiers.webhook import WebhookNotifier

# ── transport helpers ────────────────────────────────────────────────


class MockTransport(httpx.AsyncBaseTransport):
    def __init__(self, handler):
        self._handler = handler

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return self._handler(request)


def _ok_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"ok": True}, request=request)


def _error_response(status: int):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="error", request=request)

    return handler


class TimeoutTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")


def _make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=MockTransport(handler))


# ── Telegram ─────────────────────────────────────────────────────────


class TestTelegramNotifier:
    @pytest.mark.asyncio
    async def test_send_success(self):
        captured = {}

        def handler(request: httpx.Request):
            captured["url"] = str(request.url)
            captured["body"] = json.loads(request.content)
            return _ok_response(request)

        client = _make_client(handler)
        tg = TelegramNotifier("BOT_TOKEN", "CHAT_ID", client=client)
        result = await tg.send("hello")
        assert result is True
        assert "/botBOT_TOKEN/sendMessage" in captured["url"]
        assert captured["body"]["chat_id"] == "CHAT_ID"
        assert captured["body"]["text"] == "hello"
        assert captured["body"]["parse_mode"] == "HTML"
        await client.aclose()

    @pytest.mark.asyncio
    async def test_send_http_error(self):
        client = _make_client(_error_response(403))
        tg = TelegramNotifier("tok", "cid", client=client)
        result = await tg.send("fail")
        assert result is False
        await client.aclose()

    @pytest.mark.asyncio
    async def test_send_timeout(self):
        client = httpx.AsyncClient(transport=TimeoutTransport())
        tg = TelegramNotifier("tok", "cid", client=client)
        result = await tg.send("timeout")
        assert result is False
        await client.aclose()

    def test_format_new_negative_alert(self):
        suggestions = [
            {"text": "marka dolandırıcı", "score": -0.9, "category": "fraud"},
            {"text": "marka şikayet", "score": -0.6, "category": "complaint"},
        ]
        msg = TelegramNotifier.format_new_negative_alert("TestMarka", suggestions)
        assert "TestMarka" in msg
        assert "marka dolandırıcı" in msg
        assert "[fraud]" in msg
        assert "2 yeni negatif" in msg

    def test_format_daily_summary(self):
        summary = {
            "total": 10,
            "negative": 3,
            "positive": 5,
            "neutral": 2,
            "negative_ratio": 0.3,
            "avg_score": -0.1,
        }
        msg = TelegramNotifier.format_daily_summary("TestMarka", summary)
        assert "TestMarka" in msg
        assert "10" in msg
        assert "Negatif: 3" in msg
        assert "%30.0" in msg


# ── Slack ────────────────────────────────────────────────────────────


class TestSlackNotifier:
    @pytest.mark.asyncio
    async def test_send_success(self):
        captured = {}

        def handler(request: httpx.Request):
            captured["url"] = str(request.url)
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, text="ok", request=request)

        client = _make_client(handler)
        sl = SlackNotifier("https://hooks.slack.com/T/B/X", client=client)
        result = await sl.send("hello slack")
        assert result is True
        assert "hooks.slack.com" in captured["url"]
        assert captured["body"]["text"] == "hello slack"
        assert captured["body"]["mrkdwn"] is True
        await client.aclose()

    @pytest.mark.asyncio
    async def test_send_http_error(self):
        client = _make_client(_error_response(500))
        sl = SlackNotifier("https://hooks.slack.com/x", client=client)
        result = await sl.send("fail")
        assert result is False
        await client.aclose()

    @pytest.mark.asyncio
    async def test_send_timeout(self):
        client = httpx.AsyncClient(transport=TimeoutTransport())
        sl = SlackNotifier("https://hooks.slack.com/x", client=client)
        result = await sl.send("timeout")
        assert result is False
        await client.aclose()

    def test_format_new_negative_alert_mrkdwn(self):
        suggestions = [
            {"text": "brand scam", "score": -0.9, "category": "fraud"},
        ]
        msg = SlackNotifier.format_new_negative_alert("Brand", suggestions)
        assert "*Yeni Negatif" in msg
        assert "*brand scam*" in msg
        assert "`[fraud]`" in msg

    def test_format_daily_summary_mrkdwn(self):
        summary = {
            "total": 5,
            "negative": 2,
            "positive": 2,
            "neutral": 1,
            "negative_ratio": 0.4,
            "avg_score": -0.2,
        }
        msg = SlackNotifier.format_daily_summary("Brand", summary)
        assert "*Günlük Özet" in msg
        assert ":red_circle:" in msg


# ── Webhook ──────────────────────────────────────────────────────────


class TestWebhookNotifier:
    @pytest.mark.asyncio
    async def test_send_success(self):
        captured = {}

        def handler(request: httpx.Request):
            captured["body"] = json.loads(request.content)
            captured["headers"] = dict(request.headers)
            return _ok_response(request)

        client = _make_client(handler)
        wh = WebhookNotifier(
            "https://example.com/hook",
            headers={"X-Token": "abc"},
            client=client,
        )
        result = await wh.send({"event": "alert", "data": "test"})
        assert result is True
        assert captured["body"] == {"event": "alert", "data": "test"}
        assert captured["headers"].get("x-token") == "abc"
        await client.aclose()

    @pytest.mark.asyncio
    async def test_send_http_error(self):
        client = _make_client(_error_response(502))
        wh = WebhookNotifier("https://example.com/hook", client=client)
        result = await wh.send({"x": 1})
        assert result is False
        await client.aclose()

    @pytest.mark.asyncio
    async def test_send_timeout(self):
        client = httpx.AsyncClient(transport=TimeoutTransport())
        wh = WebhookNotifier("https://example.com/hook", client=client)
        result = await wh.send({"x": 1})
        assert result is False
        await client.aclose()


# ── get_notifiers factory ────────────────────────────────────────────


class FakeConfig:
    """Minimal config stub supporting dotted get()."""

    def __init__(self, data: dict):
        self._data = data

    def get(self, key: str, default=None):
        parts = key.split(".")
        node = self._data
        for p in parts:
            if isinstance(node, dict) and p in node:
                node = node[p]
            else:
                return default
        return node


class TestGetNotifiers:
    def test_no_notifiers_when_disabled(self):
        cfg = FakeConfig(
            {
                "notifications": {
                    "telegram": {"enabled": False},
                    "slack": {"enabled": False},
                }
            }
        )
        assert get_notifiers(cfg) == []

    def test_telegram_enabled(self):
        cfg = FakeConfig(
            {
                "notifications": {
                    "telegram": {"enabled": True, "bot_token": "tok", "chat_id": "cid"},
                    "slack": {"enabled": False},
                }
            }
        )
        notifiers = get_notifiers(cfg)
        assert len(notifiers) == 1
        assert isinstance(notifiers[0], TelegramNotifier)

    def test_slack_enabled(self):
        cfg = FakeConfig(
            {
                "notifications": {
                    "telegram": {"enabled": False},
                    "slack": {"enabled": True, "webhook_url": "https://hooks.slack.com/x"},
                }
            }
        )
        notifiers = get_notifiers(cfg)
        assert len(notifiers) == 1
        assert isinstance(notifiers[0], SlackNotifier)

    def test_webhook_enabled(self):
        cfg = FakeConfig(
            {
                "notifications": {
                    "telegram": {"enabled": False},
                    "slack": {"enabled": False},
                    "webhook": {"enabled": True, "url": "https://example.com/hook"},
                }
            }
        )
        notifiers = get_notifiers(cfg)
        assert len(notifiers) == 1
        assert isinstance(notifiers[0], WebhookNotifier)

    def test_multiple_notifiers(self):
        cfg = FakeConfig(
            {
                "notifications": {
                    "telegram": {"enabled": True, "bot_token": "t", "chat_id": "c"},
                    "slack": {"enabled": True, "webhook_url": "https://hooks.slack.com/x"},
                    "webhook": {"enabled": True, "url": "https://example.com/hook"},
                }
            }
        )
        notifiers = get_notifiers(cfg)
        assert len(notifiers) == 3

    def test_enabled_but_missing_credentials(self):
        cfg = FakeConfig(
            {
                "notifications": {
                    "telegram": {"enabled": True, "bot_token": "", "chat_id": ""},
                    "slack": {"enabled": True, "webhook_url": ""},
                }
            }
        )
        assert get_notifiers(cfg) == []


# ── lifecycle ────────────────────────────────────────────────────────


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_telegram_close_internal(self):
        tg = TelegramNotifier("tok", "cid")
        await tg._get_client()
        assert tg._client is not None
        await tg.close()
        assert tg._client is None

    @pytest.mark.asyncio
    async def test_slack_close_internal(self):
        sl = SlackNotifier("https://hooks.slack.com/x")
        await sl._get_client()
        await sl.close()
        assert sl._client is None

    @pytest.mark.asyncio
    async def test_webhook_close_internal(self):
        wh = WebhookNotifier("https://example.com/hook")
        await wh._get_client()
        await wh.close()
        assert wh._client is None

    @pytest.mark.asyncio
    async def test_external_client_preserved(self):
        client = httpx.AsyncClient()
        tg = TelegramNotifier("tok", "cid", client=client)
        await tg.close()
        assert tg._client is client
        await client.aclose()
