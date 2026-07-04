"""Notifications — push a message to the user's phone via a configured channel.

Supports ntfy (self-hostable, most private), Telegram, and Pushover. It only ever
sends to the user's OWN pre-configured device/topic — the agent can't choose a
recipient — so `notify` is a safe *unattended* tool: a scheduled routine can push
your morning briefing to your phone without a confirmation prompt.
"""
from __future__ import annotations

import urllib.parse
import urllib.request


def channel(config: dict | None) -> str | None:
    config = config or {}
    if config.get("ntfy_topic"):
        return "ntfy"
    if config.get("telegram_token") and config.get("telegram_chat_id"):
        return "telegram"
    if config.get("pushover_token") and config.get("pushover_user"):
        return "pushover"
    return None


def build_request(config: dict, title: str, message: str):
    """Return (url, data_bytes, headers) for the configured channel, or None."""
    ch = channel(config)
    if ch == "ntfy":
        server = (config.get("ntfy_server") or "https://ntfy.sh").rstrip("/")
        url = f"{server}/{config['ntfy_topic']}"
        headers = {"Title": title} if title else {}
        return url, (message or "").encode("utf-8"), headers
    if ch == "telegram":
        url = f"https://api.telegram.org/bot{config['telegram_token']}/sendMessage"
        text = f"*{title}*\n{message}" if title else (message or "")
        data = urllib.parse.urlencode({"chat_id": config["telegram_chat_id"],
                                       "text": text, "parse_mode": "Markdown"}).encode("utf-8")
        return url, data, {"Content-Type": "application/x-www-form-urlencoded"}
    if ch == "pushover":
        url = "https://api.pushover.net/1/messages.json"
        data = urllib.parse.urlencode({"token": config["pushover_token"],
                                       "user": config["pushover_user"],
                                       "title": title or "Myro",
                                       "message": message or ""}).encode("utf-8")
        return url, data, {"Content-Type": "application/x-www-form-urlencoded"}
    return None


def notify(config: dict, title: str = "", message: str = "") -> str:
    req = build_request(config, title, message)
    if req is None:
        return "(no notification channel — set ntfy_topic, telegram_*, or pushover_*)"
    from core.tools import _safe_urlopen
    url, data, headers = req
    try:
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with _safe_urlopen(request, timeout=15) as resp:
            resp.read(10_000)
        return f"notified via {channel(config)}"
    except Exception as e:
        return f"(error: {e})"
