"""Terminal interface — a warm, friendly, proactive REPL over the orchestrator."""
from __future__ import annotations

import os
import time

from core.proactive import Proactive
from memory.schema import Role, Source


def run_repl(orchestrator, session) -> None:
    proactive = Proactive(orchestrator.memory)
    n = _memory_count(orchestrator)
    print("\n  agi-layer — your personal intelligence layer")
    print(f"  model: {_model_status(orchestrator)}   ·   memory: {n} fact(s)"
          f"   ·   type  :help  for commands")
    if n == 0:
        print("  My memory's empty — type  :seed  to load what we already know about you.")
    else:
        q = proactive.next_question(session.active_scope)
        if q:
            print(f"  (I still don't know your {q['key']} — tell me anytime, or type  :learn.)")
    print()

    pending = None
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
            # Capture an answer to a pending active-learning question.
            if pending is not None and not line.startswith(":"):
                fact = proactive.fact_from_answer(pending, line)
                orchestrator.memory.remember(fact, scope=session.active_scope)
                print(f"Thanks — noted.  ({fact})")
                pending = None
                continue
            if line == ":learn":
                q = proactive.next_question(session.active_scope)
                if q:
                    print(q["q"])
                    pending = q
                else:
                    print("I think I've got the basics — ask me anything.")
                continue
            if line in (":briefing", ":brief"):
                facts = proactive.briefing(session.active_scope)
                if facts:
                    print("Here's what's on my radar for you:")
                    for f in facts:
                        print(f"  • {f}")
                else:
                    print("Nothing notable yet — the more we talk, the more I'll have.")
                continue
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
    if line.startswith(":ingest "):
        from memory.ingest import ingest_path
        ex = getattr(orch.memory.semantic, "extractor", None)
        r = ingest_path(orch.memory, line.split(" ", 1)[1].strip(),
                        scope=session.active_scope, extractor=ex)
        print(f"Read {r['files']} file(s) and learned {r['facts']} thing(s).")
        return True
    if line.startswith(":remember "):
        orch.memory.remember(line.split(" ", 1)[1].strip(), scope=session.active_scope)
        print("Got it — I'll remember that.")
        return True
    if line.startswith(":forget "):
        n = orch.memory.forget(line.split(" ", 1)[1].strip(), scope=session.active_scope)
        print(f"Forgot {n} memory(ies)." if n else "Nothing matched — nothing forgotten.")
        return True
    if line.startswith(":correct "):
        rest = line.split(" ", 1)[1]
        if "=>" in rest:
            old, new = (p.strip() for p in rest.split("=>", 1))
            ok = orch.memory.correct(old, new, scope=session.active_scope)
            print("Updated — thanks for the correction." if ok else "Saved the new version.")
        else:
            print("Use:  :correct <old> => <new>")
        return True
    if line.startswith(":why "):
        prov = orch.memory.provenance(line.split(" ", 1)[1].strip(), scope=session.active_scope)
        if prov:
            print("Here's what that's based on:")
            for p in prov:
                when = (time.strftime("%Y-%m-%d", time.localtime(p["created_at"]))
                        if p.get("created_at") else "earlier")
                print(f"  • {p['content']}  ({when})")
        else:
            print("I don't have a memory behind that.")
        return True
    # --- agent execution layer (do tasks, tools, automations) ---------------
    if line.startswith(":do "):
        agent = getattr(orch, "agent", None)
        if agent is None:
            print("My agent isn't available right now.")
            return True
        res = agent.run(line.split(" ", 1)[1].strip(),
                        scope=session.active_scope, confirm=_cli_confirm)
        _print_run(res)
        return True
    if line == ":tools":
        tools = getattr(orch, "tools", None)
        if tools is None:
            print("No tools registered.")
            return True
        print("Tools I can use:")
        for s in tools.specs():
            gate = "" if s["unattended"] else "  (asks first)"
            print(f"  • {s['name']}({', '.join(s['args'])}) — {s['description']}{gate}")
        return True
    if line.startswith(":automate "):
        routines = getattr(orch, "routines", None)
        rest = line.split(" ", 1)[1]
        if routines is None or "=" not in rest:
            print("Use:  :automate <name> = <task>")
            return True
        name, task = (p.strip() for p in rest.split("=", 1))
        routines.add(name, task, scope=session.active_scope)
        print(f"Saved routine “{name}”. Run it anytime with  :run {name}.")
        return True
    if line == ":routines":
        routines = getattr(orch, "routines", None)
        items = routines.list() if routines else {}
        if items:
            print("Saved routines:")
            for name, it in items.items():
                where = f"  [{it['scope']}]" if it.get("scope") else ""
                print(f"  • {name}: {it['task']}{where}")
        else:
            print("No routines yet — create one with  :automate <name> = <task>.")
        return True
    if line.startswith(":run "):
        routines = getattr(orch, "routines", None)
        if routines is None:
            print("Routines aren't available right now.")
            return True
        res = routines.run(line.split(" ", 1)[1].strip())
        if res.get("status") == "no-such-routine":
            print(f"I don't have a routine called “{res['name']}”.")
            return True
        _print_run(res)
        return True
    if line.startswith(":"):
        print(f"I don't know the command “{line}” — try  :help.")
        return True
    return False


_HELP = (
    "Commands:\n"
    "  :do <task>            let me do a task using my tools\n"
    "  :tools                what tools I can use\n"
    "  :automate <n> = <t>   save task <t> as a routine named <n>\n"
    "  :routines             list saved routines\n"
    "  :run <name>           run a saved routine (unattended)\n"
    "  :memory [topic]       what I remember (optionally about a topic)\n"
    "  :remember <fact>      tell me something to remember\n"
    "  :forget <text>        forget matching memories\n"
    "  :correct <a> => <b>   replace memory 'a' with 'b'\n"
    "  :why <topic>          what a memory is based on (+ when)\n"
    "  :ingest <path>        learn from a file or folder\n"
    "  :learn                let me ask you something to get to know you\n"
    "  :briefing             what's on my radar for you\n"
    "  :scope <name>         switch project scope (bare :scope shows current)\n"
    "  :seed                 load what we already know about you\n"
    "  :good / :bad          rate my last reply\n"
    "  :optimize             improve my routing from your feedback\n"
    "  :status / :about      status / what this is\n"
    "  exit / quit           leave\n"
    "Anything else is a message to me."
)


def _cli_confirm(tool, args) -> bool:
    """Interactive gate for tools that write or execute — default No."""
    try:
        ans = input(f"  ⚠ allow {tool}({_fmt_args(args)})? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return ans in ("y", "yes")


def _print_run(res) -> None:
    for s in res.get("steps", []):
        print(f"  · {s['tool']}({_fmt_args(s['args'])}) → {_short(s['result'])}")
    print(f"layer> {res.get('answer', '')}")


def _fmt_args(args) -> str:
    return ", ".join(f"{k}={_short(v, 40)}" for k, v in (args or {}).items())


def _short(text, limit: int = 80) -> str:
    text = str(text).replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


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
