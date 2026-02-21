"""Notification dispatchers for alerting on suggestion changes."""

from __future__ import annotations

from suggestguard.notifiers.slack import SlackNotifier
from suggestguard.notifiers.telegram import TelegramNotifier
from suggestguard.notifiers.webhook import WebhookNotifier


def get_notifiers(config) -> list:
    """Build a list of active notifier instances from *config*.

    *config* is a ``SuggestGuardConfig`` (or any object with a ``.get()``
    method).
    """
    notifiers: list = []

    tg = config.get("notifications.telegram", {})
    if tg.get("enabled") and tg.get("bot_token") and tg.get("chat_id"):
        notifiers.append(TelegramNotifier(tg["bot_token"], tg["chat_id"]))

    slack = config.get("notifications.slack", {})
    if slack.get("enabled") and slack.get("webhook_url"):
        notifiers.append(SlackNotifier(slack["webhook_url"]))

    webhook = config.get("notifications.webhook", {})
    if webhook.get("enabled") and webhook.get("url"):
        notifiers.append(
            WebhookNotifier(
                url=webhook["url"],
                headers=webhook.get("headers", {}),
            )
        )

    return notifiers
