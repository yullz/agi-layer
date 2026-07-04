"""Terminal interface — a warm, friendly REPL over the orchestrator."""
from __future__ import annotations

import os

from memory.schema import Role, Source


def run_repl(orchestrator, session) -> None:
    n = _memory_count(orchestrator)
    print("\n  agi-layer — your personal intelligence layer")
    print(f"  model: {_model_status(orchestrator)}   ·   memory: {n} fact(s)"
          f"   ·   type  :help  for commands")
    if n == 0:
        print("  My memory's empty — type  :seed  to load what we already know about you.")
    print()

    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye 👋")
            break
        if not line:
            continue
        if line in ("exit", "quit"):
            print("bye 👋")
            break
        try:  # one guard around the whole per-line body — no command can crash the REPL
            if _handle_command(line, orchestrator, session):
                continue
            reply = orchestrator.handle_turn(line, session)
            via = _last_model(session)
            print(f"layer> {reply}" + (f"   [via {via}]" if via else ""))
        except Exception as e:
            print("layer> Sorry — something went wrong on my side. Try again?")
            if os.environ.get("AGI_DEBUG"):
                print(f"       [{type(e).__name__}: {e}]")


def _handle_command(line, orch, session) -> bool:
    """Handle a ':' command / help. Returns True if the line was handled."""
    if line in (":help", "?"):
        print(_HELP)
        return True
    if line == ":about":
        print("I'm a local-first memory + model-routing layer. I remember what "
              "matters to you across sessions, keep sensitive things on your "
              "machine, and get sharper the more we talk.")
        return True
    if line == ":status":
        print(f"model: {_model_status(orch)}  ·  memory: {_memory_count(orch)} facts  ·  "
              f"scope: {session.active_scope or 'global'}  ·  "
              f"models: {', '.join(orch.router.registry.names())}")
        return True
    if line == ":scope":
        print(f"scope: {session.active_scope or 'global'}")
        return True
    if line.startswith(":scope "):
        session.set_scope(line.split(" ", 1)[1].strip() or None)
        print(f"[scope -> {session.active_scope or 'global'}]")
        return True
    if line in (":good", ":bad"):
        orch.feedback.rate(session.session_id, 1.0 if line == ":good" else -1.0)
        print("Thanks — noted." if line == ":good" else "Got it, I'll do better.")
        return True
    if line == ":optimize":
        print(_optimize_msg(orch.optimize()))
        return True
    if line in (":memory", ":recall") or line.startswith((":memory ", ":recall ")):
        q = line.split(" ", 1)[1].strip() if " " in line else ""
        bundle = orch.memory.retrieve(q, scope=session.active_scope, budget_tokens=1500)
        # Show durable memory (facts + graph relations), not raw conversation turns.
        durable = [c for c in bundle.items if c.source in (Source.VECTOR, Source.GRAPH)]
        if durable:
            print("Here's what I remember" + (f" about “{q}”" if q else "") + ":")
            for c in durable[:8]:
                print(f"  • {c.content}")
        else:
            print("I don't have anything relevant remembered yet.")
        return True
    if line == ":seed":
        from memory.seed import seed_memory
        r = seed_memory(orch.memory)
        if r.get("facts") or r.get("relations"):
            print(f"Loaded {r['facts']} facts and {r['relations']} connections about you "
                  f"— try  :memory  to see them.")
        else:
            print("Hmm, I couldn't load the seed data.")
        return True
    if line.startswith(":"):
        print(f"I don't know the command “{line}” — try  :help.")
        return True
    return False


_HELP = (
    "Commands:\n"
    "  :help / ?          show this\n"
    "  :memory [topic]    what I remember (optionally about a topic)\n"
    "  :scope <name>      switch project scope (bare :scope shows current)\n"
    "  :seed              load what we already know about you\n"
    "  :good / :bad       rate my last reply\n"
    "  :optimize          improve my routing from your feedback\n"
    "  :status            models + memory status\n"
    "  :about             what this is\n"
    "  exit / quit        leave\n"
    "Anything else is a message to me."
)


def _optimize_msg(res) -> str:
    s = (res or {}).get("status")
    return {
        "applied": f"Updated my routing (v{(res or {}).get('version')}).",
        "no-change": "Nothing to change yet — I need a bit more feedback first.",
        "denied-by-governance": "I found a tweak, but my guardrails held it back.",
    }.get(s, "My improvement loop isn't available right now.")


def _memory_count(orch) -> int:
    sem = getattr(orch.memory, "semantic", None)
    fn = getattr(sem, "count_all", None) or getattr(sem, "count_current", None)
    try:
        return fn() if fn else 0
    except Exception:
        return 0


def _model_status(orch) -> str:
    reg = getattr(orch.router, "registry", None)
    if reg is None:
        return "echo · offline"
    for name in reg.names():
        if name == "echo":
            continue
        m = reg.get(name)
        probe = getattr(m, "available", None)
        try:
            if callable(probe) and probe():
                return name
        except Exception:
            continue
    return "echo · offline"


def _last_model(session):
    for m in reversed(getattr(session, "messages", [])):
        role = m.role.value if isinstance(m.role, Role) else m.role
        if role == "assistant":
            mn = getattr(m, "model", None)
            if not mn:
                return None
            return "echo · offline" if mn == "echo" else mn
    return None
