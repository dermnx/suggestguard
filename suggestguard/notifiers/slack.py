"""Slack webhook notification sender."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Send alerts to a Slack channel via an Incoming Webhook."""

    def __init__(
        self,
        webhook_url: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.webhook_url = webhook_url
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
        """Post a mrkdwn message to Slack. Returns True on success."""
        client = await self._get_client()
        payload = {
            "text": message,
            "mrkdwn": True,
        }
        try:
            resp = await client.post(self.webhook_url, json=payload)
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("Slack HTTP %s: %s", exc.response.status_code, exc.response.text)
            return False
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.error("Slack connection error: %s", exc)
            return False

    # ── formatters ───────────────────────────────────────────────────

    @staticmethod
    def format_new_negative_alert(brand_name: str, suggestions: list[dict]) -> str:
        """Format an alert for newly detected negative suggestions (mrkdwn)."""
        lines = [f":rotating_light: *Yeni Negatif Öneriler — {brand_name}*", ""]
        for s in suggestions:
            score = s.get("score", "")
            cat = s.get("category") or ""
            cat_str = f" `[{cat}]`" if cat else ""
            lines.append(f"• *{s['text']}*  ({score}){cat_str}")
        lines.append("")
        lines.append(f"Toplam: {len(suggestions)} yeni negatif öneri")
        return "\n".join(lines)

    @staticmethod
    def format_daily_summary(brand_name: str, summary: dict) -> str:
        """Format a daily summary message (mrkdwn)."""
        neg = summary.get("negative", 0)
        pos = summary.get("positive", 0)
        neu = summary.get("neutral", 0)
        total = summary.get("total", 0)
        ratio = summary.get("negative_ratio", 0)
        avg = summary.get("avg_score", 0)

        return (
            f":bar_chart: *Günlük Özet — {brand_name}*\n"
            f"\n"
            f"Toplam öneri: {total}\n"
            f":red_circle: Negatif: {neg}  |  "
            f":large_green_circle: Pozitif: {pos}  |  "
            f":white_circle: Nötr: {neu}\n"
            f"Negatif oran: %{ratio * 100:.1f}\n"
            f"Ortalama skor: {avg}"
        )
