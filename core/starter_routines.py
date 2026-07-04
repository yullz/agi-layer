"""Prebuilt starter routines — useful automations out of the box.

Installed on demand (`:starters` in the CLI, or `install_starters`). They're
added *unscheduled* — nothing runs on a clock until you opt in with `:schedule`,
so the layer never does background work you didn't ask for. Each carries a
suggested schedule you can copy.

All of them stay within the unattended tool set (search/browse/read/recall/
remember), so they're safe to run automatically — a routine never writes files
or runs shell commands.
"""
from __future__ import annotations

STARTERS = [
    {
        "name": "morning",
        "task": ("Search the web for today's most important AI and technology "
                 "news. Pick the top 3 stories, summarize each in one sentence "
                 "with its link, then remember the result as today's briefing."),
        "scope": None,
        "suggest": "at 08:00",
        "about": "Morning briefing — top AI/tech stories, saved to memory.",
    },
    {
        "name": "linkdigest",
        "task": ("Read the file links.txt. For each URL in it, fetch the page and "
                 "write a one-line summary of what it is about. Produce a short "
                 "digest covering all of them and remember it as my link digest."),
        "scope": None,
        "suggest": "at 18:00",
        "about": "Inbox-of-links digest — drop URLs in links.txt, get summaries.",
    },
    {
        "name": "recap",
        "task": ("Recall what I am currently working on and what matters to me, "
                 "and give me a short recap of where things stand."),
        "scope": None,
        "suggest": "every 480m",
        "about": "Project recap — a memory-only 'where things stand' summary.",
    },
    {
        "name": "phone_briefing",
        "task": ("Get today's most important AI and technology news from the web, "
                 "and check my calendar for today's events. Then send me a push "
                 "notification titled 'Morning briefing' with the top 3 stories and "
                 "a one-line summary of my schedule."),
        "scope": None,
        "suggest": "at workstart",
        "about": "Morning phone briefing — news + today's calendar, pushed to your phone.",
    },
    {
        "name": "eod_recap",
        "task": ("Recap my day: summarize my recent git commits and what I worked "
                 "on from memory, and note anything still open. Then send me a push "
                 "notification titled 'End of day' with a short recap."),
        "scope": None,
        "suggest": "at workend",
        "about": "End-of-day recap — what you did + what's open, pushed to your phone.",
    },
]


def install_starters(routines) -> list:
    """Add any missing starter routines (idempotent, unscheduled).
    Returns the names actually added."""
    existing = routines.list()
    added = []
    for s in STARTERS:
        if s["name"] in existing:
            continue
        routines.add(s["name"], s["task"], scope=s.get("scope"))
        added.append(s["name"])
    return added
