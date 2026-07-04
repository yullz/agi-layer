"""Telegram interface — the real long-poll transport for the bridge.

Run with AGI_INTERFACE=telegram and AGI_TELEGRAM_TOKEN / AGI_TELEGRAM_CHAT_ID set
(create a bot with @BotFather; get your chat id by messaging the bot and reading
getUpdates). The routing/auth logic lives in core/telegram_bridge.py; this file
is just the HTTP client that talks to Telegram's API.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

from core.telegram_bridge import TelegramBridge


class _TelegramClient:
    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}"

    def get_updates(self, offset: int):
        url = f"{self.base}/getUpdates?timeout=30&offset={int(offset)}"
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                data = json.loads(r.read(2_000_000).decode("utf-8", errors="ignore"))
            return data.get("result", []) if data.get("ok") else []
        except Exception:
            return []

    def send_message(self, chat_id, text: str):
        url = f"{self.base}/sendMessage"
        body = urllib.parse.urlencode({"chat_id": chat_id, "text": text or ""}).encode("utf-8")
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, data=body), timeout=20) as r:
                r.read(10_000)
        except Exception:
            pass


def serve_telegram(orchestrator, cfg) -> None:
    token = getattr(cfg, "telegram_token", None)
    if not token:
        print("Telegram not configured — set AGI_TELEGRAM_TOKEN (and AGI_TELEGRAM_CHAT_ID).")
        return
    bridge = TelegramBridge(orchestrator, _TelegramClient(token),
                            getattr(cfg, "telegram_chat_id", None))
    name = getattr(getattr(orchestrator, "context_builder", None), "assistant_name", "Myro")
    print(f"{name} is listening on Telegram — text your bot to talk to him. Ctrl-C to stop.")
    bridge.run()
