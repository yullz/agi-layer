"""Telegram bridge — text Myro from your phone, anywhere.

Long-polls Telegram for messages and, for the AUTHORIZED chat only, runs each
through the orchestrator and replies. Two safety properties:

  - Auth: messages from any chat other than the configured chat_id are ignored,
    so finding the bot isn't enough to talk to your Myro.
  - Non-interactive: turns run with confirm=None, so read-only tools work but
    gated writes (send email, create issue, run shell…) are denied fail-closed —
    a text can't trigger a destructive action without a confirmation you can't
    give over this channel.

The transport is injected (a client with get_updates/send_message), so the
routing logic is fully testable without a network. It needs your PC (or a small
always-on box) running this interface to be reachable while you're away; it uses
outbound long-polling, so no public IP or port-forwarding is required.
"""
from __future__ import annotations

from core.session import Session


class TelegramBridge:
    def __init__(self, orchestrator, client, chat_id, scope: str | None = None):
        self.orch = orchestrator
        self.client = client
        self.chat_id = str(chat_id) if chat_id is not None else None
        self.session = Session(scope=scope)
        self._offset = 0

    def handle_update(self, update) -> bool:
        msg = (update or {}).get("message") or {}
        chat = str((msg.get("chat") or {}).get("id", ""))
        text = (msg.get("text") or "").strip()
        if not text:
            return False
        if self.chat_id and chat != self.chat_id:
            return False                          # ignore anyone but the owner
        try:
            reply = self.orch.handle_turn(text, self.session, confirm=None)
        except Exception:
            reply = "Sorry — something went wrong on my side."
        self.client.send_message(chat, reply or "(no reply)")
        return True

    def poll_once(self) -> int:
        updates = self.client.get_updates(self._offset) or []
        handled = 0
        for u in updates:
            uid = u.get("update_id")
            if uid is not None:
                self._offset = max(self._offset, uid + 1)
            if self.handle_update(u):
                handled += 1
        return handled

    def run(self) -> None:      # pragma: no cover (blocking network loop)
        while True:
            try:
                self.poll_once()
            except Exception:
                pass
