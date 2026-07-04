"""Context builder — assembles the final prompt (a messages list) from memory + session."""
from __future__ import annotations

from core.session import Session
from memory.schema import ContextBundle, Role

_SYSTEM = (
    "You are agi-layer, a personal intelligence layer that remembers the user "
    "across sessions. Use the retrieved memory below when relevant; if it "
    "conflicts with what the user just said, trust the user and note the change. "
    "Active scope: {scope}."
)


class ContextBuilder:
    def build(self, session: Session, ctx: ContextBundle, model) -> list[dict]:
        """Compose an OpenAI/LiteLLM/Ollama-style messages list:
          1. system instructions (+ active scope)
          2. retrieved memory block (already budget-packed) + dropped note
          3. recent working-memory turns (includes the current user input)
        """
        messages: list[dict] = [
            {"role": "system",
             "content": _SYSTEM.format(scope=session.active_scope or "global")}
        ]

        if ctx.items:
            lines = [f"- {c.content}" for c in ctx.items if c.content]
            block = "Relevant memory:\n" + "\n".join(lines)
            if ctx.summary_of_dropped:
                block += f"\n{ctx.summary_of_dropped}"
            messages.append({"role": "system", "content": block})

        for ep in session.recent():
            role = ep.role.value if isinstance(ep.role, Role) else str(ep.role)
            if role not in ("user", "assistant", "system"):
                role = "user"
            messages.append({"role": role, "content": ep.content})

        return messages
