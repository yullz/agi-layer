"""Orchestrator — the turn loop that ties the whole layer together.

Read -> route -> assemble -> generate -> write, with feedback captured for the
improvement loop and consolidation running out of band on a scheduler. The
improvement loop (`optimize`) is governed: proposals are guardrail-gated,
snapshotted, and audited before they touch the live routing policy.
"""
from __future__ import annotations

from core.session import Session
from memory.schema import Turn


class Orchestrator:
    def __init__(self, *, memory, router, context_builder, skills, feedback,
                 retrieval_budget_tokens: int = 6000,
                 optimizer=None, policy=None, guardrails=None,
                 versioning=None, audit=None):
        self.memory = memory
        self.router = router
        self.context_builder = context_builder
        self.skills = skills
        self.feedback = feedback
        self.budget = retrieval_budget_tokens
        # Improvement + governance (optional; enable self.optimize()).
        self.optimizer = optimizer
        self.policy = policy
        self.guardrails = guardrails
        self.versioning = versioning
        self.audit = audit

    def handle_turn(self, user_input: str, session: Session, confirm=None) -> str:
        session.add_user(user_input)
        scope = session.active_scope

        # ROUTE FIRST — so retrieval can be destination-aware: if the answer is
        # going to a non-local model, sensitive-scope memory must be withheld.
        model = self.router.pick(user_input, None, scope=scope)
        for_external = not getattr(model, "is_local", False)

        # READ — scoped, budget-packed, privacy-filtered context.
        ctx = self.memory.retrieve(user_input, scope=scope,
                                   budget_tokens=self.budget, for_external=for_external)
        messages = self.context_builder.build(session, ctx, model)

        # ASSEMBLE + GENERATE. With a capable (tool-following) model wired to the
        # agent, plain natural language runs through the conversational agent loop
        # so the model can DECIDE to act (calling tools, gated ones via `confirm`)
        # or just answer. Offline/echo degrades to a straight generate.
        self.last_steps = []
        if self._agent_capable(model):
            result = self.agent.converse(messages, scope=scope, confirm=confirm)
            reply = result.get("answer", "")
            self.last_steps = result.get("steps", [])
            used = result.get("model", model)
        else:
            used, reply = self.router.generate(
                model, messages, tools=self.skills.available(scope=scope))

        model_name = getattr(used, "model_name", None)
        session.add_assistant(reply, model=model_name)

        # WRITE + capture signal for the improvement loop.
        self.memory.write(Turn.from_session(session))
        self.feedback.observe(session, reply, model=model_name)
        return reply

    def _agent_capable(self, model) -> bool:
        """Route conversational turns through the agent only when there's an
        agent wired AND the model can follow the tool protocol. The offline echo
        model can't, so it uses the plain generate path (today's behavior)."""
        if getattr(self, "agent", None) is None or getattr(self, "tools", None) is None:
            return False
        name = (getattr(model, "model_name", "") or "").lower()
        return name != "echo"

    def optimize(self) -> dict:
        """One governed self-improvement step: propose a better routing policy
        from feedback, gate it through guardrails, snapshot + audit it, then
        apply it to the live policy. Off the hot path (call on a schedule or
        via the CLI ':optimize')."""
        if not (self.optimizer and self.policy):
            return {"status": "unavailable"}
        proposal = self.optimizer.propose(self.policy, self.feedback.recent())
        if proposal is None:
            return {"status": "no-change"}
        approved = self.optimizer.apply(
            self.policy, proposal, guardrails=self.guardrails,
            versioning=self.versioning, audit=self.audit)
        if approved is None:
            return {"status": "denied-by-governance"}
        # Apply in place so the router (which shares this Policy) uses it now.
        self.policy.routing_rules = approved.routing_rules
        self.policy.version = approved.version
        return {"status": "applied", "version": approved.version,
                "routing_rules": approved.routing_rules}
