# Phase 20 — Reach Myro anywhere: voice, phone notifications, texting

Three ways to connect with Myro beyond the terminal: he can **speak**, **push to
your phone**, and be **texted from anywhere** via Telegram. Credentials come from
env vars, so nothing secret lives in code.

## 1. Voice (`core/voice.py`)

`:voice on` speaks Myro's replies aloud through a **local** TTS engine —
pyttsx3 if installed, else a platform command (`say` on macOS, `spd-say`/`espeak`
on Linux, PowerShell SAPI on Windows). No cloud, no key. If no engine is found it
degrades to a clean no-op (voice is always optional). Start with it on via
`AGI_VOICE=on` or `voice_enabled` in config.

```
:voice on      # speak replies
:voice off     # back to text
```

## 2. Phone notifications (`core/notify.py` + the `notify` tool)

Push a message to your phone through a configured channel:

- **ntfy** — self-hostable, most private (`AGI_NTFY_TOPIC`, optional `AGI_NTFY_SERVER`); install the ntfy app and subscribe to your topic.
- **Telegram** — `AGI_TELEGRAM_TOKEN` + `AGI_TELEGRAM_CHAT_ID`.
- **Pushover** — `AGI_PUSHOVER_TOKEN` + `AGI_PUSHOVER_USER`.

Exposed as the **`notify`** tool. It's **unattended** — because it can only reach
*your own* configured device (the agent can't pick a recipient), a scheduled
routine can safely push without a confirmation prompt. So:

```
:automate morning = summarize today's AI news and notify me the top 3
:schedule morning at workstart      # briefing lands on your phone at your 9am
```

## 3. Text Myro from your phone (`core/telegram_bridge.py` + `interfaces/telegram.py`)

Run the Telegram interface and DM your bot from anywhere:

```bash
AGI_INTERFACE=telegram AGI_TELEGRAM_TOKEN=… AGI_TELEGRAM_CHAT_ID=… python main.py
```

It long-polls Telegram (outbound only — **no public IP or port-forwarding**),
runs each message through the orchestrator, and replies in the chat. Two safety
properties, both tested:

- **Authorized-chat-only**: messages from any chat other than your
  `chat_id` are ignored — finding the bot isn't enough to talk to your Myro.
- **Non-interactive**: turns run with `confirm=None`, so read-only tools and
  `notify` work, but **gated writes** (send email, create issue, run shell, add a
  calendar event) are **denied fail-closed** — a text can't trigger a destructive
  action without a confirmation you can't give over the wire.

## Setup summary (env vars)

```bash
export AGI_VOICE=on                       # speak replies (local)
export AGI_NTFY_TOPIC=myro-<random>       # phone push via ntfy (subscribe in the app)
export AGI_TELEGRAM_TOKEN=123:abc         # @BotFather bot token
export AGI_TELEGRAM_CHAT_ID=987654        # your chat id (from getUpdates)
```

Also newly env-configurable: `AGI_ASSISTANT_NAME`, `AGI_USER_NAME`,
`AGI_TIMEZONE`, `AGI_GITHUB_TOKEN`, `AGI_GITHUB_REPO`.

## The one caveat

Myro runs on **your** machine, so your PC (or a small always-on box — a Pi or a
cheap VPS) must be running the Telegram interface to receive texts / push while
you're away. Anything routed through Telegram/Pushover touches their servers;
**self-hosted ntfy** keeps notifications fully private.

## Verify (offline)

```bash
python3 tests/smoke.py     # 155 checks; section 32 covers voice + notify + bridge
```

Section 32 verifies (no network): voice degrades cleanly and toggles; the ntfy /
Telegram / Pushover request payloads are built correctly and channel precedence
is right; and the Telegram bridge relays **only** the authorized chat, runs turns
non-interactively (gated writes denied), and advances its offset without
re-processing. Wiring confirmed through `main.build()`: the `notify` tool appears
(unattended) only when a channel is configured.

## Notes / follow-ups

- Voice speaks synchronously (fine for short replies); a background/streaming
  voice is a refinement.
- The bridge is one authorized chat; multi-user or per-scope chats would be a
  small extension. Telegram is the reference transport — the same
  `TelegramBridge` core could sit behind Slack/SMS with a different client.
