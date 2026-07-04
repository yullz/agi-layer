"""Voice interface — hands-free: talk to Myro, he talks back.

Run with AGI_INTERFACE=voice. Needs a microphone plus a local speech-to-text
engine (Whisper or Vosk) and a TTS engine; if any is missing it explains what to
install and exits cleanly. The loop itself lives in core/voice_loop.py.
"""
from __future__ import annotations

from core.voice_loop import VoiceLoop, WakeLoop


def serve_voice(orchestrator, cfg=None) -> None:
    listener = getattr(orchestrator, "listener", None)
    speaker = getattr(orchestrator, "speaker", None)
    name = getattr(getattr(orchestrator, "context_builder", None), "assistant_name", "Myro")
    if listener is None or not listener.available():
        print("Voice input isn't available. Install SpeechRecognition + a local STT "
              "engine (openai-whisper or vosk) and a microphone backend (e.g. pyaudio).")
        return
    if speaker is not None:
        speaker.enabled = True

    def _echo(heard, reply):
        print(f"you (voice)> {heard}")
        print(f"{name}> {reply}")

    wake = getattr(cfg, "wake_word", "Myro") if cfg is not None else "Myro"
    if wake:
        print(f"{name} is listening for '{wake}'. Say e.g. \"{wake}, what's my "
              f"schedule?\"  ·  say 'stop listening' to end.")
        WakeLoop(orchestrator, listener, speaker, wake=wake).run(on_turn=_echo)
    else:
        print(f"{name} is listening — just talk. Say 'stop listening' to end.")
        VoiceLoop(orchestrator, listener, speaker).run(on_turn=_echo)
