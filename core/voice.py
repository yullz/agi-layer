"""Voice — optional local text-to-speech so Myro can speak his replies.

Tries an offline engine first (pyttsx3), then a platform TTS command
(macOS `say`, Linux `spd-say`/`espeak`, Windows PowerShell SAPI). If none is
available, `speak()` is a no-op that returns False — voice is always optional and
never blocks or crashes the REPL. Runs fully on your machine (no cloud).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

_MAX_SPOKEN = 600   # keep spoken replies short


class Speaker:
    def __init__(self, enabled: bool = False):
        self.enabled = bool(enabled)
        self._backend = None          # None = undetected, False = none available

    def available(self) -> bool:
        return self._detect() is not None

    def toggle(self, on: bool | None = None) -> bool:
        self.enabled = (not self.enabled) if on is None else bool(on)
        return self.enabled

    def speak(self, text: str, force: bool = False) -> bool:
        """Speak `text` if voice is enabled (or force=True, for the `speak`
        tool / voice replies). Returns True if it actually spoke."""
        if not text or not (self.enabled or force):
            return False
        backend = self._detect()
        if backend is None:
            return False
        try:
            return bool(backend(str(text)[:_MAX_SPOKEN]))
        except Exception:
            return False

    # --- backend detection --------------------------------------------------
    def _detect(self):
        if self._backend is None:
            self._backend = self._pick() or False
        return self._backend or None

    def _pick(self):
        try:
            import pyttsx3   # offline, cross-platform

            def _say(text):
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
                return True
            return _say
        except Exception:
            pass
        if sys.platform == "darwin" and shutil.which("say"):
            return lambda t: subprocess.run(["say", t], timeout=90).returncode == 0
        for cmd in ("spd-say", "espeak-ng", "espeak"):
            if shutil.which(cmd):
                return lambda t, c=cmd: subprocess.run([c, t], timeout=90).returncode == 0
        if os.name == "nt" and shutil.which("powershell"):
            def _win_say(t):
                # Embed the (single-quote-escaped) text into the script — passing
                # it as a trailing arg to -Command doesn't bind to $args reliably.
                safe = str(t).replace("'", "''")
                ps = ("Add-Type -AssemblyName System.Speech; "
                      "(New-Object System.Speech.Synthesis.SpeechSynthesizer)"
                      f".Speak('{safe}')")
                return subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                                      timeout=90).returncode == 0
            return _win_say
        return None
