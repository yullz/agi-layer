"""VoiceLoop — fully hands-free: listen, answer, speak, repeat.

One cycle = capture speech -> transcribe -> run the turn -> speak the reply. The
listener and speaker are injected, so the loop logic is testable without a mic or
a TTS engine. Turns run with a confirm callback (interactive) or None; over a
non-interactive setup, gated writes stay denied fail-closed.

Say a stop phrase ("stop listening", "goodbye Myro", …) to end.
"""
from __future__ import annotations

from core.session import Session

STOP_PHRASES = {"stop listening", "stop", "goodbye myro", "bye myro", "exit", "quit"}
_STOP = "__stop__"


class VoiceLoop:
    def __init__(self, orchestrator, listener, speaker, confirm=None, scope=None):
        self.orch = orchestrator
        self.listener = listener
        self.speaker = speaker
        self.confirm = confirm
        self.session = Session(scope=scope)

    def once(self):
        """Run one listen->answer->speak cycle. Returns (heard, reply):
        (None, None) if nothing was heard; ('__stop__', None) on a stop phrase."""
        text = self.listener.listen()
        if not text:
            return (None, None)
        if text.strip().lower() in STOP_PHRASES:
            return (_STOP, None)
        try:
            reply = self.orch.handle_turn(text, self.session, confirm=self.confirm)
        except Exception:
            reply = "Sorry — something went wrong on my side."
        try:
            self.speaker.speak(reply, force=True)
        except Exception:
            pass
        return (text, reply)

    def run(self, on_turn=None) -> None:   # pragma: no cover (blocking mic loop)
        while True:
            heard, reply = self.once()
            if heard == _STOP:
                break
            if heard and callable(on_turn):
                on_turn(heard, reply)
