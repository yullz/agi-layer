"""Claude via the Claude Agent SDK — runs on your Pro/Max subscription.

Uses the Agent SDK's auth (OAuth login via `claude login`), so calls draw from
your Claude plan instead of metered API credits. Requires
`pip install claude-agent-sdk` and a logged-in Claude CLI (or ANTHROPIC_API_KEY
as a fallback the SDK will also accept). Import/auth failures make available()
return False, so the router simply won't route here.

Note: subscription usage is rate-limited by your plan's window — fine for a
personal, single-user layer; heavy automated volume can hit caps.
"""
from __future__ import annotations

import asyncio

is_local = False  # external provider — never used for sensitive scopes


class AgentSDKModel:
    is_local = False

    def __init__(self, name: str, model: str | None = None, **opts):
        self.model_name = name
        self.model = model  # optional explicit Claude model id; None = plan default
        self.effort = opts.pop("effort", None)  # quick | balanced | thorough
        self.opts = opts

    def available(self) -> bool:
        try:
            import claude_agent_sdk  # noqa: F401
            return True
        except Exception:
            return False

    def generate(self, prompt, tools=None) -> str:
        try:
            return asyncio.run(self._agenerate(prompt))
        except RuntimeError:
            # Already inside a running event loop — run in a worker thread.
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(lambda: asyncio.run(self._agenerate(prompt))).result()

    async def _agenerate(self, prompt) -> str:
        from claude_agent_sdk import ClaudeAgentOptions, query
        system, user = _split(prompt)
        system = _apply_effort(system, self.effort)
        opts: dict = {}
        if system:
            opts["system_prompt"] = system
        if self.model:
            opts["model"] = self.model
        options = ClaudeAgentOptions(**opts) if opts else None
        chunks: list[str] = []
        async for message in query(prompt=user or " ", options=options):
            for block in getattr(message, "content", []) or []:
                text = getattr(block, "text", None)
                if text:
                    chunks.append(text)
        return "".join(chunks).strip()


_EFFORT_HINT = {
    "quick": "Answer briefly and directly — as few words as the question needs.",
    "thorough": "Think it through carefully and reason step by step before "
                "answering; be thorough and complete.",
}


def _apply_effort(system: str, effort) -> str:
    """Steer how hard Claude works via a system directive (balanced = default)."""
    hint = _EFFORT_HINT.get(str(effort or "").lower())
    if not hint:
        return system
    return (system.rstrip() + "\n\n" + hint) if system else hint


def _split(prompt):
    """Turn a messages list into (system_text, single_user_prompt) for the SDK."""
    if isinstance(prompt, str):
        return "", prompt
    systems, convo = [], []
    for m in prompt if isinstance(prompt, list) else []:
        if not isinstance(m, dict):
            continue
        role, content = m.get("role"), str(m.get("content", ""))
        if role == "system":
            systems.append(content)
        elif role == "assistant":
            convo.append(f"Assistant: {content}")
        else:
            convo.append(f"User: {content}")
    return "\n\n".join(systems), "\n".join(convo)
