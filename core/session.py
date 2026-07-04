"""Session — working memory for the turn in flight.

Holds the running message list and the active scope (which project/domain the
conversation is about). Scope drives memory filtering on both read and write, so
set it deliberately — switching projects should switch scope, or an Ocado query
starts pulling YouTube facts.
"""
from __future__ import annotations

from memory.schema import Episode, Role, Turn, _id, _now


class Session:
    def __init__(self, scope: str | None = None):
        self.session_id = _id()
        self.active_scope = scope
        self.messages: list[Episode] = []

    def add_user(self, content: str) -> None:
        self.messages.append(Episode(
            session_id=self.session_id, role=Role.USER,
            content=content, scope=self.active_scope,
        ))

    def add_assistant(self, content: str, model: str | None = None) -> None:
        self.messages.append(Episode(
            session_id=self.session_id, role=Role.ASSISTANT,
            content=content, scope=self.active_scope, model=model,
        ))

    def recent(self, n: int = 12) -> list[Episode]:
        return self.messages[-n:]

    def set_scope(self, scope: str | None) -> None:
        self.active_scope = scope

    def to_turn(self) -> Turn:
        user = next((m.content for m in reversed(self.messages) if m.role == Role.USER), "")
        asst = next((m.content for m in reversed(self.messages) if m.role == Role.ASSISTANT), "")
        return Turn(
            session_id=self.session_id, scope=self.active_scope,
            user_input=user, assistant_reply=asst, ts=_now(),
        )
