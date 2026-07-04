# Meet Myro — everything he can do

A plain-English guide to your assistant. No jargon. If you only read one file to
understand what Myro is and what you can do with him, read this one.

*(New here? To install and start him, see **[docs/SETUP.md](./docs/SETUP.md)**.
Not sure what's installed? Double-click **`Doctor.bat`**.)*

---

## Who is Myro?

Myro is **your own private AI that lives on your computer.** Think of him as a
personal assistant who:

- **Remembers you** — across days, weeks, forever. Tell him something once and he
  keeps it.
- **Stays private** — he runs on *your* machine. Nothing leaves it unless you
  choose to connect a cloud brain or let him use the web.
- **Actually does things** — not just chat. He can check your calendar, send an
  email, open a web page, run a daily routine, and more — when you ask.
- **Gets more useful over time** — the more you tell him, the better he knows how
  to help.

He's not a website or an app you log into. He's a program you run, and he's
*yours*.

---

## Four ways to talk to him

| Way | How | Best for |
|---|---|---|
| 💬 **Browser app** | Double-click **`Myro.bat`** | Everyday use — a clean chat window with all his features |
| ⌨️ **Terminal** | `python main.py` | Quick, keyboard-only, no browser |
| 🎤 **Voice** | Say **"Hey Myro"** | Hands-free — talk, he talks back |
| 📱 **Your phone** | Text him on **Telegram** | Reaching him when you're away from your PC |

You can use any of them — it's the same Myro, with the same memory, underneath.

---

## What he can do

### 1. 🧠 Remembers what matters

Just tell him things, and he keeps them. He also quietly notices and remembers
important facts as you chat.

> *"Remember that my sister's birthday is March 3rd."*
> *"My main project this quarter is the Riverside launch."*
> *"What do you remember about my work?"*
> *"Forget what I said about the old apartment."*

He sorts out duplicates, updates facts when they change, and gently lets old,
unused details fade — like a real memory.

### 2. 💭 Thinks and answers with you

Ask him anything, brainstorm, draft, summarize, plan. He talks like a
collaborator who knows you, not a search box.

> *"Help me write a polite email declining a meeting."*
> *"What should I focus on today?"*
> *"Explain compound interest simply."*

### 3. 🖐️ Actually does things — just ask in plain words

This is the big one. You don't need special commands — **just describe what you
want** and Myro figures out which of his tools to use.

**Two speeds, for your safety:**
- ✅ **Safe things happen instantly** — reading, looking things up, math, remembering.
- 🔒 **Things that change or send something ask you first** — sending an email,
  writing a file, opening an issue. He shows you what he's about to do and waits
  for a yes. (And automated routines are *never* allowed to do these — they fail
  safely.)

Here's the full toolbox:

| Area | He can… | Try saying |
|---|---|---|
| 📅 **Calendar** | See what's coming up · add an event 🔒 | *"What's on my calendar this week?"* · *"Add lunch with Sam Friday at 1pm"* |
| 📧 **Email** | Read recent messages · send one 🔒 | *"Any important emails today?"* · *"Email Alex that I'll be 10 minutes late"* |
| 🐙 **GitHub & code** | Show recent activity, issues, PRs · open an issue 🔒 · read your git history | *"What issues are open on my repo?"* · *"Open an issue: login button is broken"* |
| 🌐 **The web** | Search · read a page · browse & click through sites | *"Search for the best budget laptops 2026"* · *"Read this article and summarize it"* |
| 📂 **Your files** | List a folder · read a file · write one 🔒 | *"What's in my Documents folder?"* · *"Save these notes to ideas.txt"* |
| ⚡ **Quick stuff** | Do math · tell the time/date | *"What's 18% of 240?"* · *"What time is it?"* |
| 🔔 **Reach you** | Send a notification to your phone | *"Remind my phone to leave at 5"* |

*(Anything with a 🔒 asks for your confirmation first. Some tools — email,
GitHub — need a quick one-time setup with your account details; see
[docs/SETUP.md](./docs/SETUP.md).)*

### 4. ⏰ Runs on a schedule (automations)

Myro can do things **automatically**, on a schedule you set — so useful stuff
happens without you asking.

He comes with ready-made routines you can turn on:

| Routine | What it does |
|---|---|
| **morning** | A morning brief — your day, ahead of you |
| **linkdigest** | Rounds up interesting links |
| **recap** | A midday catch-up |
| **phone_briefing** | Sends a briefing straight to your phone |
| **eod_recap** | An end-of-day wrap-up |
| **backup** | Quietly backs up everything overnight |

And you can create your own in plain words:

> *"Every morning at 8am, give me a summary of my calendar."*
> *"Remind me to stretch every 90 minutes."*

Schedules understand things like `at 08:00`, `every 30 minutes`, and even `at
workstart` / `workend` — which line up with **your** working hours (he learned
those when he introduced himself).

### 5. 🎤 Talks and listens

- **He can speak his answers out loud** — flip on the 🔊 button in the app, or use
  `:voice` in the terminal.
- **You can talk to him** — tap the 🎤 mic in the app and just speak.
- **Wake word:** say **"Hey Myro"** and he starts listening, hands-free.

### 6. 📱 Reaches your phone

- **Notifications:** Myro can ping your phone (via free apps like ntfy, or
  Telegram/Pushover) — for reminders, briefings, or when a routine finishes.
- **Text him anywhere:** connect Telegram and you can message Myro from your
  phone like any chat — he answers with your memory and tools behind him.

### 7. 💾 Backs everything up

One command (or a nightly routine) snapshots **everything you've built** — your
memories, routines, and settings — into a safe archive. It can be **encrypted**
before it leaves your machine, and optionally pushed to a **private GitHub repo**
so you never lose your Myro, even if your PC dies.

> *In the app: Settings → "Back up now". In the terminal: `:backup`.*

---

## 🔒 Your privacy, by design

This is the whole point of Myro living on your machine:

- **Local-first.** By default, everything stays on your computer. Nothing is sent
  anywhere unless *you* switch on a cloud brain or let him use the web.
- **Sensitive things stay local.** Anything you mark private is only ever handled
  by the on-your-machine model — it never goes to the cloud, even if you use a
  cloud brain for everything else.
- **Actions ask permission.** Sending, writing, and posting always wait for your
  yes. Background routines can't do those at all.
- **You own your data.** It all lives in a folder called `data/` inside Myro.
  It's yours — copy it, back it up, move it. Updating Myro's code never touches it.

---

## 🧠 His brain (how smart he is)

Myro can think using different "brains" — you pick:

| Brain | What it is | Privacy |
|---|---|---|
| **Ollama (local)** | AI models running on your own PC — free, offline | 🟢 100% private |
| **Claude (subscription)** | Uses your Claude Pro/Max plan — sharpest answers | Cloud |
| **Echo (built-in)** | A tiny offline fallback so Myro always runs | 🟢 100% private |

Out of the box he uses the echo fallback (so he *always* works). Add Ollama or
Claude to make him genuinely smart — see **[docs/SETUP.md](./docs/SETUP.md)**,
Step 4.

**You choose how he picks.** If both a local model and Claude are set up, Myro
normally routes everyday chat to Claude (sharpest) and keeps anything *private*
on the local model. Prefer to keep **everything** local — private and free? Flip
**Settings → Brain → "Prefer my local model"** in the app (or set
`AGI_PREFER_LOCAL=on`). Sensitive things stay local either way.

---

## ⌨️ Handy terminal commands

If you're in the terminal, type `:help` to see these any time:

| Command | Does |
|---|---|
| `:help` | List everything he can do |
| `:remember` / `:recall` / `:forget` | Manage memories by hand |
| `:memory` | Show what he remembers |
| `:do <task>` | Ask him to do something with his tools |
| `:automate` / `:routines` / `:schedule` | Create and schedule automations |
| `:starters` | Turn on the ready-made routines |
| `:voice` / `:listen` | Turn speaking / listening on |
| `:backup` | Back everything up now |
| `:connectors` / `:tools` | See what's connected and available |
| `:profile` / `:onboard` | Your details / redo the introduction |
| `:status` | What model and memory he's using |

*(In the browser app, all of this is in the sidebar — Chat, Memory, Routines,
Connectors, Settings — no commands to remember.)*

---

## Where to go next

- **Install & switch on features:** [docs/SETUP.md](./docs/SETUP.md)
- **Check what's installed:** double-click `Doctor.bat`
- **How he's built (for the curious):** [ARCHITECTURE.md](./ARCHITECTURE.md)

That's Myro — a private assistant who remembers you, does real things when you
ask, and is entirely yours. 🚀
