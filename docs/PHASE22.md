# Phase 22 — Voice input + a `speak` tool (hands-free Myro)

Two additions that complete the voice loop from Phase 20: Myro can now **listen**
(speech-to-text) and expose **speaking as a tool**, so you can talk to him
hands-free and routines can read things aloud.

## 1. `speak` tool (`core/tools.py` + `core/voice.py`)

A new **`speak`** tool reads text aloud on your machine via the shared local TTS
`Speaker`. It's **unattended** (local audio only — nothing leaves the machine and
nothing changes), so a routine can speak:

```
:automate deskbrief = get today's AI news, summarize the top 3, and read it aloud
:schedule deskbrief at workstart
```

`Speaker.speak(text, force=True)` speaks even when the `:voice` reply-toggle is
off, so the tool always works when an engine is present. One shared `Speaker`
backs replies, the `:voice` toggle, and this tool.

## 2. Voice input (`core/listen.py`, `core/voice_loop.py`, `interfaces/voice.py`)

- **`Listener`** captures a mic utterance and transcribes it — **offline-first**:
  it prefers a local recognizer (Whisper — great on your GPU — or Vosk) so audio
  never leaves your machine. No SpeechRecognition, engine, or mic → `available()`
  is False and `listen()` returns None (always optional, never crashes).
- **`:listen`** (in the text REPL) captures one spoken message and runs it as a
  turn, then speaks the reply.
- **`AGI_INTERFACE=voice`** runs a fully hands-free loop (`VoiceLoop`): listen →
  answer → speak → repeat. Say **"stop listening"** to end. The loop I/O is
  injected, so its logic is tested without a mic.

Turns from voice run through the same `handle_turn`, so gated writes still prompt
(CLI) or are denied (non-interactive) — voice doesn't bypass the safety gate.

Enable it:

```bash
pip install "agi-layer[voice,voice-input]"   # pyttsx3 + SpeechRecognition
pip install openai-whisper                    # local STT (or: pip install vosk + a model)
# plus a mic backend (e.g. pyaudio) for your OS
```
```
:listen                       # talk once, in the text REPL
AGI_INTERFACE=voice python main.py   # fully hands-free
```

## Verify (offline)

```bash
python3 tests/smoke.py     # 164 checks; section 33 covers voice I/O
```

Section 33 verifies (no mic, no engine): the `speak` tool registers unattended
and returns a string (degrading cleanly with no engine); `speak(force=…)` never
crashes; the `Listener` degrades cleanly when unavailable; and the `VoiceLoop`
(with injected fakes) transcribes → answers → speaks, stops on a stop phrase, and
ignores empty input.

## Notes

- STT is offline-first by design — it will not silently send your audio to a
  cloud recognizer; install Whisper or Vosk for private transcription.
- Whisper on the RTX 4070 transcribes near-instantly; Vosk is lighter if you want
  minimal footprint.
- The `VoiceLoop` is transport-agnostic — the same core could sit behind a phone
  call or a wake-word front end later.
