# Setting up Myro — a friendly guide

Myro is your personal AI that runs on **your own computer**. This guide gets you
from zero to talking to him. No prior experience needed — copy, paste, done.

**The good news:** Myro runs out of the box with **nothing installed** beyond the
basics. Everything else (a smarter brain, voice, your phone) is optional and you
can add it whenever you like.

---

## Step 1 — Install Python (one time)

Myro needs **Python 3.11 or newer**. Check if you already have it:

```bash
python --version        # Windows might use:  py --version
```

If it says 3.11 or higher, you're set. If not, install it from
**https://python.org/downloads** (tick *"Add Python to PATH"* on Windows).

## Step 2 — Get Myro running

In a terminal (Command Prompt / PowerShell on Windows, Terminal on Mac/Linux),
go to the `agi-layer` folder, then:

```bash
# 1) create a private workspace for Myro's dependencies
python -m venv .venv

# 2) turn it on
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1

# 3) install Myro
pip install -e .

# 4) start him
python main.py
```

That's it. The first time, **Myro introduces himself and asks you ~13 quick
questions** to get to know you (press Enter to skip any, or type `stop`). After
that you're at the `you>` prompt — just talk to him.

> Out of the box he uses a tiny built-in "echo" brain so everything runs with
> zero setup. To make him genuinely smart, do **Step 4**.

Type `:help` any time to see what he can do, and `exit` to leave.

## Step 3 — Check everything's healthy (optional)

```bash
python tests/smoke.py        # should print "All 169 checks PASS"
```

If that passes, your install is good.

---

## ⭐ Use Myro as an app (no terminal)

Prefer a real chat window instead of the terminal? Myro has a clean browser app.

```bash
pip install -e ".[serve]"        # one-time
python main.py                    # from the Myro folder — with AGI_INTERFACE=api set
```
…or, easiest of all, **double-click `Myro.bat`** (Windows) / run `./myro.sh`
(Mac/Linux). Your browser opens to Myro's chat app automatically.

It's a full interface: chat with message bubbles, a 🎤 talk button and 🔊 speak
toggle (voice, nothing to install), and tabs for your **Memory**, **Routines**
(create + schedule), **Connectors**, and **Settings** (name / timezone / theme).
It's **100% local** — the page is served from your own PC; nothing goes online
unless you turn on a cloud brain or the web tools.

> Tip: create a desktop shortcut to `Myro.bat` and you've got a one-click app.

---

## Step 4 — Give Myro a real brain (pick one, or both)

**Option A — Claude on your subscription (recommended, best quality).**
Uses your Claude Pro/Max plan, not pay-per-use credits.

```bash
pip install -e ".[subscription]"
claude login            # opens your browser to sign in
```
Restart Myro. `:status` should show a `claude` model, and his replies tag
`[via claude-…]`.

**Option B — A local model (fully private, works offline).**
Runs entirely on your machine — great for a private setup or no internet.

```bash
# install Ollama first from https://ollama.com, then:
ollama pull qwen3:14b        # fits a 16GB GPU like an RTX 4070
```
Restart Myro; he'll use it automatically. Anything you mark **private** always
goes to this local model, never the cloud.

**Sharper memory (optional but nice):**
```bash
pip install -e ".[rerank]"   # real embeddings — much better recall
```

---

## Step 5 — Optional superpowers

Add any of these whenever you want. Each is independent.

### 🌐 Browse the web (including logins & JavaScript pages)
```bash
pip install -e ".[browser]"
playwright install chromium
```
Now: *"search the web for…"*, *"browse this page and summarize it"*.

### 🔊 Let Myro speak, and 🎤 talk to him
```bash
pip install -e ".[voice,voice-input]"
pip install openai-whisper           # local speech-to-text (private)
# you also need a microphone library for your OS, e.g.:  pip install pyaudio
```
- `:voice on` — he reads his replies aloud.
- `:listen` — talk one message at a time.
- **Hands-free with a wake word:**
  ```bash
  AGI_INTERFACE=voice python main.py
  ```
  Then just say **"Hey Myro, what's on my calendar?"** He waits for his name, does
  it, speaks the answer, and waits again. Say **"stop listening"** to end.
  (Change the wake word with `AGI_WAKE_WORD=Jarvis`.)

### 📱 Reach your phone (notifications + text him from anywhere)
Most private option is **ntfy** (free app, self-hostable):
```bash
export AGI_NTFY_TOPIC=myro-<make-up-something-random>
```
Install the **ntfy** app on your phone and subscribe to that same topic. Now
routines can push to you — try:
```
:starters
:schedule phone_briefing at workstart     # a morning briefing on your phone
```

**Text Myro from anywhere** with a Telegram bot:
1. In Telegram, message **@BotFather**, send `/newbot`, follow the prompts, copy the token.
2. Message your new bot once, then run this and note your chat id (the number under `"chat":{"id":…}`):
   ```bash
   AGI_TELEGRAM_TOKEN=your-token python main.py     # then in another terminal, or just set both below
   ```
3. Start the bridge:
   ```bash
   AGI_INTERFACE=telegram AGI_TELEGRAM_TOKEN=your-token AGI_TELEGRAM_CHAT_ID=your-id python main.py
   ```
Now you can text your bot from your phone and Myro replies. (He only answers
*your* chat, and won't do anything destructive over text without you at the
keyboard.)

> Note: for phone features, your computer needs to be **on and running Myro**
> while you're away.

### 💾 Back up everything you've built
Myro can snapshot his memory so you never lose it. Easiest private setup — send
snapshots to a folder your cloud drive already syncs:
```bash
export AGI_BACKUP_DIR="$HOME/OneDrive/Myro-backups"   # or Dropbox/Google Drive
export AGI_BACKUP_PASSPHRASE="a long phrase you'll remember"   # encrypt them (recommended)
pip install -e ".[backup]"                            # for encryption
```
Then click **"Back up now"** in the app's Settings, type `:backup` in the
terminal, or install the nightly routine: `:starters` then
`:schedule backup at 02:00`. Prefer GitHub? Clone a **private** backup repo and
set `AGI_BACKUP_GIT_DIR` to it — Myro pushes each snapshot there.

> Your memory is personal — if backups leave your machine (cloud drive or
> GitHub), set a passphrase so they're encrypted.

---

## Step 6 — Settings & secrets (env vars)

You never have to edit code. Set these in your terminal (or a `.env` file) before
starting Myro:

| Setting | What it does |
|---|---|
| `AGI_ASSISTANT_NAME` | rename him (default `Myro`) |
| `AGI_USER_NAME` | so he greets you by name |
| `AGI_TIMEZONE` | your timezone (e.g. `Europe/Berlin`) for scheduling |
| `AGI_VOICE=on` | speak replies by default |
| `AGI_WAKE_WORD` | the hands-free wake word (default `Myro`) |
| `AGI_NTFY_TOPIC` | phone notifications via ntfy |
| `AGI_TELEGRAM_TOKEN` / `AGI_TELEGRAM_CHAT_ID` | text him via Telegram |
| `AGI_GITHUB_TOKEN` | let him read private repos / open issues |
| `AGI_INTERFACE` | `cli` (default) · `voice` · `telegram` · `api` · `mcp` |

Myro also derives your timezone and working hours from the onboarding questions,
so `:schedule … at workstart` lines up with your real day. See them with
`:profile`.

---

## Everyday commands

```
just type normally     ask a question, or ask him to do something
:do <task>             force him to use his tools
:memory                what he remembers  ·  :why <topic>  where it came from
:remember <fact>       tell him something to keep
:ingest <path>         learn from a file or folder
:connectors            status of git / calendar / email / github
:starters              install ready-made routines
:automate n = task     save a routine  ·  :schedule n at 08:00  ·  :run n
:voice on  ·  :listen  speak replies · talk to him
:profile               your name / timezone / working hours
:help                  the full list
```

---

## Troubleshooting

- **"command not found: python"** → try `py` (Windows) or `python3` (Mac/Linux).
- **Replies are short/robotic** → you're on the built-in echo brain; do **Step 4**.
- **Voice says "no engine"** → install `pyttsx3` (`pip install pyttsx3`) or your OS
  voice; for input install `openai-whisper` + a mic library.
- **Nothing happens on the wake word** → speak clearly and include his name
  (*"Hey Myro, …"*); make sure your mic works and Whisper/Vosk is installed.
- **Start fresh** → your data lives in the `data/` folder; delete it to reset
  (this erases his memory).

## Where your stuff lives — and privacy

Everything Myro knows is in the **`data/`** folder on your machine. Nothing leaves
your computer unless *you* turn on a cloud brain or a phone channel. Private
scopes always stay local, and Myro asks before anything that sends or changes
something.
