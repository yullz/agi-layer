"""Orchestrator — the turn loop that ties the whole layer together.

Read -> route -> assemble -> generate -> write, with feedback captured for the
improvement loop and consolidation running out of band on a scheduler. This
function is the spine; everything else is depth behind the contracts it calls.
"""
from __future__ import annotations

from core.session import Session
from memory.schema import Turn


class Orchestrator:
    def __init__(self, *, memory, router, context_builder, skills, feedback,
                 retrieval_budget_tokens: int = 6000):
        self.memory = memory
        self.router = router
        self.context_builder = context_builder
        self.skills = skills
        self.feedback = feedback
        self.budget = retrieval_budget_tokens

    def handle_turn(self, user_input: str, session: Session) -> str:
        session.add_user(user_input)

        # READ — pull scoped, budget-packed context from memory.
        ctx = self.memory.retrieve(
            user_input,
            scope=session.active_scope,
            budget_tokens=self.budget,
        )

        # ROUTE + ASSEMBLE — pick a model, build the prompt.
        model = self.router.pick(user_input, ctx)
        prompt = self.context_builder.build(session, ctx, model)

        # GENERATE — the tool loop lives inside the model adapter.
        reply = model.generate(
            prompt,
            tools=self.skills.available(scope=session.active_scope),
        )
        session.add_assistant(reply, model=getattr(model, "model_name", None))

        # WRITE (async) + capture signal for the improvement loop.
        self.memory.write(Turn.from_session(session))
        self.feedback.observe(session, reply)

        return reply
