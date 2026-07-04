"""First-boot onboarding — a short interview so Myro knows you from the start.

On the very first interactive boot, Myro asks a handful of introductory
questions and stores each answer as a durable memory (global/identity scope), so
from turn one it actually knows who you are, what you're working on, and how you
like to be helped. It runs once — a small JSON marker in the data dir records
that it's done (and remembers your name for the welcome-back greeting).
"""
from __future__ import annotations

import json
import os

# 13 questions — kept in the 10-15 range, one per line of who-you-are. Each has a
# first-person `fact` template so the stored memory reads like the user talking
# ("My name is …"), which is how the rest of the system phrases facts.
QUESTIONS = [
    {"key": "name",
     "q": "First things first — what should I call you?",
     "fact": "My name is {a}."},
    {"key": "role",
     "q": "What do you do — your work or main focus these days?",
     "fact": "I work on / focus on {a}."},
    {"key": "projects",
     "q": "What are you working on right now that I should keep track of?",
     "fact": "I'm currently working on {a}."},
    {"key": "location",
     "q": "Where are you based? (a city or timezone helps me with timing)",
     "fact": "I'm based in {a}."},
    {"key": "hours",
     "q": "When are you usually working or most active?",
     "fact": "My usual working hours are {a}."},
    {"key": "tools",
     "q": "What tools, languages, or apps do you use most?",
     "fact": "The tools I use most are {a}."},
    {"key": "goals",
     "q": "What's a goal you're chasing that I can help with?",
     "fact": "One of my goals is {a}."},
    {"key": "interests",
     "q": "Outside of work, what are you into?",
     "fact": "Outside work I'm into {a}."},
    {"key": "communication",
     "q": "How do you like me to communicate — brief and direct, detailed, casual, formal?",
     "fact": "I prefer communication that is {a}."},
    {"key": "help",
     "q": "What would make me most useful to you day to day?",
     "fact": "I'd find Myro most useful for {a}."},
    {"key": "people",
     "q": "Anyone important I should know about — teammates, family, clients?",
     "fact": "Important people in my life: {a}."},
    {"key": "avoid",
     "q": "Anything I should avoid, or that tends to annoy you?",
     "fact": "Something to avoid with me: {a}."},
    {"key": "hopes",
     "q": "Last one — what are you hoping to get out of working with me?",
     "fact": "What I'm hoping to get from Myro: {a}."},
]

_SKIP = {"", "skip", "pass", "-", "n/a", "none"}
_STOP = {"stop", "quit", "done", "exit", ":skip"}


class Onboarding:
    def __init__(self, path):
        self.path = str(path)
        self._state = self._load()

    def questions(self) -> list:
        return list(QUESTIONS)

    def is_done(self) -> bool:
        return bool(self._state.get("done"))

    def name(self) -> str | None:
        return self._profile().get("name")

    def timezone(self) -> str | None:
        return self._profile().get("timezone")

    def work_start(self) -> str | None:
        return self._profile().get("work_start")

    def work_end(self) -> str | None:
        return self._profile().get("work_end")

    def _profile(self) -> dict:
        return self._state.get("profile") or {}

    @staticmethod
    def is_skip(answer: str) -> bool:
        return (answer or "").strip().lower() in _SKIP

    @staticmethod
    def is_stop(answer: str) -> bool:
        return (answer or "").strip().lower() in _STOP

    def record(self, memory, question: dict, answer: str, scope=None) -> str:
        """Store one answer as a durable fact; returns the fact text."""
        fact = question["fact"].format(a=answer.strip())
        try:
            memory.remember(fact, scope=scope)
        except Exception:
            pass
        return fact

    def complete(self, profile: dict | None = None) -> None:
        self._state["done"] = True
        if profile:
            self._state["profile"] = {**(self._state.get("profile") or {}), **profile}
        self._save()

    # --- persistence --------------------------------------------------------
    def _load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save(self) -> None:
        d = os.path.dirname(self.path)
        if d:
            os.makedirs(d, exist_ok=True)
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2)
        except Exception:
            pass
