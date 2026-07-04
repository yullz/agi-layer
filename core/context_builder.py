"""Context builder — assembles the final prompt (a messages list) from memory + session."""
from __future__ import annotations

from core.session import Session
from memory.schema import ContextBundle, Role

_SYSTEM = (
    "You are the user's personal intelligence layer — a sharp, warm, concise "
    "assistant who genuinely knows them and gets better over time.{who} Speak "
    "naturally, like a trusted collaborator, not a database. When the memory "
    "below is relevant, weave it in conversationally rather than dumping facts; "
    "if it conflicts with what the user just said, trust them and note the change. "
    "Be brief by default, ask a clarifying question when the request is ambiguous, "
    "and never invent memories you don't have. Active scope: {scope}."
)


class ContextBuilder:
    def __init__(self, user_name: str | None = None):
        self.user_name = user_name

    def build(self, session: Session, ctx: ContextBundle, model) -> list[dict]:
        who = f" You're speaking with {self.user_name}." if self.user_name else ""
        messages: list[dict] = [
            {"role": "system",
             "content": _SYSTEM.format(scope=session.active_scope or "global", who=who)}
        ]

        if ctx.items:
            lines = [f"- {c.content}" for c in ctx.items if c.content]
            block = "What you remember that may be relevant:\n" + "\n".join(lines)
            if ctx.summary_of_dropped:
                block += f"\n{ctx.summary_of_dropped}"
            messages.append({"role": "system", "content": block})

        for ep in session.recent():
            role = ep.role.value if isinstance(ep.role, Role) else str(ep.role)
            if role not in ("user", "assistant", "system"):
                role = "user"
            messages.append({"role": role, "content": ep.content})

        return messages
