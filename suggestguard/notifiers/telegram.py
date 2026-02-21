"""Telegram bot notification sender."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


class TelegramNotifier:
    """Send alerts via the Telegram Bot API."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
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

    # ── send ─────────────────────────────────────────────────────────

    async def send(self, message: str) -> bool:
        """Send a Telegram message. Returns True on success."""
        client = await self._get_client()
        url = f"{TELEGRAM_API}/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
        }
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("Telegram HTTP %s: %s", exc.response.status_code, exc.response.text)
            return False
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.error("Telegram connection error: %s", exc)
            return False

    # ── formatters ───────────────────────────────────────────────────

    @staticmethod
    def format_new_negative_alert(brand_name: str, suggestions: list[dict]) -> str:
        """Format an alert for newly detected negative suggestions."""
        lines = [f"🚨 <b>Yeni Negatif Öneriler — {brand_name}</b>", ""]
        for s in suggestions:
            score = s.get("score", "")
            cat = s.get("category") or ""
            cat_str = f" [{cat}]" if cat else ""
            lines.append(f"• <b>{s['text']}</b>  ({score}){cat_str}")
        lines.append("")
        lines.append(f"Toplam: {len(suggestions)} yeni negatif öneri")
        return "\n".join(lines)

    @staticmethod
    def format_daily_summary(brand_name: str, summary: dict) -> str:
        """Format a daily summary message."""
        neg = summary.get("negative", 0)
        pos = summary.get("positive", 0)
        neu = summary.get("neutral", 0)
        total = summary.get("total", 0)
        ratio = summary.get("negative_ratio", 0)
        avg = summary.get("avg_score", 0)

        return (
            f"📊 <b>Günlük Özet — {brand_name}</b>\n"
            f"\n"
            f"Toplam öneri: {total}\n"
            f"🔴 Negatif: {neg}  |  🟢 Pozitif: {pos}  |  ⚪ Nötr: {neu}\n"
            f"Negatif oran: %{ratio * 100:.1f}\n"
            f"Ortalama skor: {avg}"
        )
