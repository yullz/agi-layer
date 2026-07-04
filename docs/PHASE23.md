# Phase 23 — Wake word ("Hey Myro") + a beginner-friendly setup guide

The hands-free voice interface now waits for a **wake word** — Myro only acts
after you call his name — and `docs/SETUP.md` is rewritten for a first-timer.

## Wake word (`core/voice_loop.py` → `WakeLoop`)

`AGI_INTERFACE=voice` now runs a `WakeLoop`: it listens continuously but does
nothing until it hears the wake word (default **"Myro"**). Everything after the
wake word is the command:

- *"Hey Myro, what's on my calendar?"* → runs it, speaks the answer, waits again.
- *"Myro"* alone → he says **"Yes?"**, then takes your next sentence as the command.
- Anything without the wake word → ignored.
- *"stop listening"* → ends.

Wake matching is **word-boundary** aware (so "myron" doesn't trigger it), and the
wake word is configurable via `AGI_WAKE_WORD` / `wake_word` in settings (set it
empty for continuous listening with no wake word — the old `VoiceLoop`). The loop
I/O is injected, so the logic is tested without a mic.

## Beginner-friendly setup (`docs/SETUP.md`)

Rewritten as a plain-language, copy-paste walkthrough: install Python → get Myro
running (with the first-boot interview) → give him a real brain (Claude
subscription or local Qwen) → optional superpowers (browser, voice + wake word,
phone notifications, texting via Telegram) → a settings/secrets table → an
everyday-commands cheat sheet → troubleshooting → where your data lives + privacy.

## Verify (offline)

```bash
python3 tests/smoke.py     # 169 checks; section 34 covers the wake word
```

Section 34 verifies (no mic): wake word + command in one breath runs the command;
no wake word does nothing; the wake word alone acknowledges and takes the next
utterance; a stop phrase ends it; and word-boundary matching avoids false
triggers ("myron" ≠ "Myro").

## Notes

- Wake detection is STT-based (reuses Whisper/Vosk) — no extra dependency or model.
  A dedicated low-latency wake engine (Porcupine/openWakeWord) could slot in
  behind the same loop later.
