"""VoiceLoop — fully hands-free: listen, answer, speak, repeat.

One cycle = capture speech -> transcribe -> run the turn -> speak the reply. The
listener and speaker are injected, so the loop logic is testable without a mic or
a TTS engine. Turns run with a confirm callback (interactive) or None; over a
non-interactive setup, gated writes stay denied fail-closed.

Say a stop phrase ("stop listening", "goodbye Myro", …) to end.
"""
from __future__ import annotations

import re

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


class WakeLoop:
    """Always-listening: only acts after the wake word ("Hey Myro"), so nothing
    happens until you call his name. Everything after the wake word (in the same
    breath, or the next one) is the command; it runs, he speaks, and it goes back
    to waiting. Same injected I/O, so the logic is testable without a mic."""

    def __init__(self, orchestrator, listener, speaker, wake: str = "Myro",
                 confirm=None, scope=None):
        self.orch = orchestrator
        self.listener = listener
        self.speaker = speaker
        self.wake = (wake or "Myro").strip().lower()
        self.confirm = confirm
        self.session = Session(scope=scope)

    def _command_after_wake(self, text: str):
        """Return the command following the wake word (possibly ''), or None if
        the wake word wasn't spoken."""
        m = re.search(r"\b" + re.escape(self.wake) + r"\b", text.lower())
        if not m:
            return None
        return text[m.end():].lstrip(" ,.:;-—?!")

    def _run(self, command: str):
        try:
            reply = self.orch.handle_turn(command, self.session, confirm=self.confirm)
        except Exception:
            reply = "Sorry — something went wrong on my side."
        try:
            self.speaker.speak(reply, force=True)
        except Exception:
            pass
        return reply

    def once(self):
        """Wait for one utterance. Returns (command, reply): (None, None) if not
        woken / nothing heard; ('__stop__', None) on a stop phrase."""
        heard = self.listener.listen()
        if not heard:
            return (None, None)
        if heard.strip().lower() in STOP_PHRASES:
            return (_STOP, None)
        command = self._command_after_wake(heard)
        if command is None:
            return (None, None)                 # wake word not spoken — keep waiting
        if not command:
            # Woken with no command in the same breath — acknowledge, then listen.
            try:
                self.speaker.speak("Yes?", force=True)
            except Exception:
                pass
            command = self.listener.listen()
            if not command:
                return (None, None)
            if command.strip().lower() in STOP_PHRASES:
                return (_STOP, None)
        return (command, self._run(command))

    def run(self, on_turn=None) -> None:   # pragma: no cover (blocking mic loop)
        while True:
            command, reply = self.once()
            if command == _STOP:
                break
            if command and callable(on_turn):
                on_turn(command, reply)
