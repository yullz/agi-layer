"""Listen — optional speech-to-text so you can talk to Myro hands-free.

Offline-first and private: it uses the SpeechRecognition library for mic capture
and prefers a LOCAL recognizer — Whisper (great on a GPU) or Vosk — so audio never
leaves your machine. If SpeechRecognition, an offline engine, or a microphone
isn't available, `available()` is False and `listen()` returns None — voice input
is always optional and never crashes.

Enable it with:  pip install SpeechRecognition openai-whisper   (+ a mic backend,
e.g. pyaudio), or  pip install SpeechRecognition vosk  with a downloaded model.
"""
from __future__ import annotations

import json


class Listener:
    def __init__(self, timeout: float = 8.0, phrase_limit: float = 15.0):
        self.timeout = timeout
        self.phrase_limit = phrase_limit
        self._backend = None          # None = undetected, False = unavailable

    def available(self) -> bool:
        return self._detect() is not None

    def listen(self) -> str | None:
        """Capture one utterance from the mic and transcribe it, or None."""
        backend = self._detect()
        if backend is None:
            return None
        recognizer, mic, transcribe = backend
        try:
            with mic as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = recognizer.listen(source, timeout=self.timeout,
                                          phrase_time_limit=self.phrase_limit)
            text = transcribe(recognizer, audio)
            return (text or "").strip() or None
        except Exception:
            return None

    # --- backend detection --------------------------------------------------
    def _detect(self):
        if self._backend is None:
            self._backend = self._pick() or False
        return self._backend or None

    def _pick(self):
        try:
            import speech_recognition as sr
        except Exception:
            return None
        try:
            mic = sr.Microphone()
        except Exception:
            return None                      # no mic / no pyaudio backend
        transcribe = self._offline_recognizer()
        if transcribe is None:
            return None                      # no private/offline engine installed
        return sr.Recognizer(), mic, transcribe

    @staticmethod
    def _offline_recognizer():
        try:
            import whisper  # noqa: F401  (local Whisper, best on a GPU)
            return lambda r, a: r.recognize_whisper(a, language="english")
        except Exception:
            pass
        try:
            import vosk  # noqa: F401
            return lambda r, a: (json.loads(r.recognize_vosk(a) or "{}").get("text", ""))
        except Exception:
            pass
        return None
