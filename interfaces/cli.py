"""Terminal interface — a warm, friendly, proactive REPL over the orchestrator."""
from __future__ import annotations

import os
import time

from core.proactive import Proactive
from memory.schema import Role, Source


def run_repl(orchestrator, session) -> None:
    proactive = Proactive(orchestrator.memory)
    name = _assistant_name(orchestrator)
    onboarding = getattr(orchestrator, "onboarding", None)
    n = _memory_count(orchestrator)
    print(f"\n  {name} — your personal intelligence layer")
    print(f"  model: {_model_status(orchestrator)}   ·   memory: {n} fact(s)"
          f"   ·   type  :help  for commands")

    if onboarding is not None and not onboarding.is_done():
        # First interactive boot: get to know the user.
        _run_onboarding(orchestrator, session, onboarding, name)
    else:
        who = onboarding.name() if onboarding else None
        if who:
            print(f"  Welcome back, {who}.")
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
            # Plain natural language: the orchestrator routes to the agent when a
            # capable model is connected, so it can act (gated tools prompt via
            # _cli_confirm) or just answer. Show any tool activity it performed.
            reply = orchestrator.handle_turn(line, session, confirm=_cli_confirm)
            for s in getattr(orchestrator, "last_steps", None) or []:
                print(f"  · {s['tool']}({_fmt_args(s['args'])}) → {_short(s['result'])}")
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
        print(f"I'm {_assistant_name(orch)} — your local-first memory + model-routing "
              "layer. I remember what matters to you across sessions, keep sensitive "
              "things on your machine, and get sharper the more we talk.")
        return True
    if line in (":onboard", ":intro"):
        onboarding = getattr(orch, "onboarding", None)
        if onboarding is None:
            print("Onboarding isn't available right now.")
            return True
        _run_onboarding(orch, session, onboarding, _assistant_name(orch), rerun=True)
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
    if line == ":connectors":
        from core.connectors import connector_status
        conf = getattr(orch, "connectors", None)
        if conf is None:
            print("Connectors are disabled (allow_connectors = False).")
            return True
        print("Connectors (git / calendar / email):")
        for name, state in connector_status(conf).items():
            mark = "✓" if state.startswith("ok") else "·"
            print(f"  {mark} {name}: {state}")
        print("Set calendar_file / mailbox_file / git_repo in config to wire them up.")
        return True
    if line == ":starters":
        from core.starter_routines import STARTERS, install_starters
        routines = getattr(orch, "routines", None)
        if routines is None:
            print("Routines aren't available right now.")
            return True
        added = install_starters(routines)
        print(f"Added {len(added)} starter routine(s): {', '.join(added)}."
              if added else "Starter routines are already installed.")
        print("What they do:")
        for s in STARTERS:
            print(f"  • {s['name']} — {s['about']}")
        print("Try one now:  :run morning   ·   schedule it:  :schedule morning at 08:00")
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
        from core.routines import describe_schedule
        routines = getattr(orch, "routines", None)
        items = routines.list() if routines else {}
        if items:
            print("Saved routines:")
            for name, it in items.items():
                where = f"  [{it['scope']}]" if it.get("scope") else ""
                sched = describe_schedule(it)
                tag = f"  ⏰ {sched}" if sched else ""
                last = f"\n      last: {_short(it['last_result'])}" if it.get("last_result") else ""
                print(f"  • {name}: {it['task']}{where}{tag}{last}")
        else:
            print("No routines yet — type  :starters  for ready-made ones, or "
                  "create your own with  :automate <name> = <task>.")
        return True
    if line.startswith(":schedule "):
        routines = getattr(orch, "routines", None)
        if routines is None:
            print("Routines aren't available right now.")
            return True
        ok, msg = _apply_schedule(routines, line.split(" ", 1)[1].strip())
        print(msg)
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
    "  :do <task>            force a task through my tools (also happens in chat)\n"
    "  :tools                what tools I can use\n"
    "  :connectors           status of git / calendar / email connectors\n"
    "  :starters             install ready-made routines (briefing, digest…)\n"
    "  :automate <n> = <t>   save task <t> as a routine named <n>\n"
    "  :schedule <n> ...     schedule a routine: every <N>m | at <HH:MM> | off\n"
    "  :routines             list saved routines (+ schedules, last result)\n"
    "  :run <name>           run a saved routine now (unattended)\n"
    "  :memory [topic]       what I remember (optionally about a topic)\n"
    "  :remember <fact>      tell me something to remember\n"
    "  :forget <text>        forget matching memories\n"
    "  :correct <a> => <b>   replace memory 'a' with 'b'\n"
    "  :why <topic>          what a memory is based on (+ when)\n"
    "  :ingest <path>        learn from a file or folder\n"
    "  :learn                let me ask you something to get to know you\n"
    "  :onboard              (re)run the introductory interview\n"
    "  :briefing             what's on my radar for you\n"
    "  :scope <name>         switch project scope (bare :scope shows current)\n"
    "  :seed                 load what we already know about you\n"
    "  :good / :bad          rate my last reply\n"
    "  :optimize             improve my routing from your feedback\n"
    "  :status / :about      status / what this is\n"
    "  exit / quit           leave\n"
    "Otherwise just talk to me — ask a question or ask me to do something, and\n"
    "I'll answer or take the action (I'll ask before anything that writes or sends)."
)


def _apply_schedule(routines, rest: str):
    """Parse ':schedule <name> every 30m' | '<name> at 08:00' | '<name> off'."""
    parts = rest.split()
    if len(parts) < 2:
        return False, "Use:  :schedule <name> every <N>m  |  at <HH:MM>  |  off"
    name, verb, arg = parts[0], parts[1].lower(), (parts[2] if len(parts) > 2 else "")
    if name not in routines.list():
        return False, f"I don't have a routine called “{name}”."
    if verb in ("off", "none", "never"):
        routines.unschedule(name)
        return True, f"Cleared the schedule for “{name}”."
    if verb == "every":
        mins = _minutes(arg or verb)
        if not mins:
            return False, "Use:  :schedule <name> every <N>m  (e.g. every 30m)"
        routines.schedule(name, every_minutes=mins)
        return True, f"“{name}” will run every {mins}m."
    if verb == "at":
        if ":" not in arg:
            return False, "Use:  :schedule <name> at <HH:MM>  (e.g. at 08:00)"
        routines.schedule(name, at=arg)
        return True, f"“{name}” will run daily at {arg}."
    return False, "Use:  :schedule <name> every <N>m  |  at <HH:MM>  |  off"


def _minutes(token: str):
    try:
        return int((token or "").lower().rstrip("m").strip())
    except Exception:
        return None


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


def _assistant_name(orch) -> str:
    cb = getattr(orch, "context_builder", None)
    return getattr(cb, "assistant_name", "Myro") or "Myro"


def _run_onboarding(orch, session, onboarding, name, rerun: bool = False) -> None:
    """Ask the introductory questions and store each answer as a durable memory."""
    qs = onboarding.questions()
    if rerun:
        print(f"\n  Let's (re)do introductions — {len(qs)} quick questions.")
    else:
        print(f"\n  Hi — I'm {name}. Before we start, can I ask you {len(qs)} quick "
              "questions")
        print("  so I actually know you from the start?")
    print("  (Press Enter to skip any · type 'stop' to finish early.)\n")
    profile = {}
    for i, q in enumerate(qs, 1):
        try:
            ans = input(f"  [{i}/{len(qs)}] {q['q']}\n  you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if onboarding.is_stop(ans):
            break
        if onboarding.is_skip(ans):
            continue
        onboarding.record(orch.memory, q, ans, scope=None)
        if q["key"] == "name":
            profile["name"] = ans
            try:
                orch.context_builder.user_name = ans
            except Exception:
                pass
    onboarding.complete(profile)
    who = profile.get("name") or onboarding.name()
    hi = f", {who}" if who else ""
    print(f"\n  Thanks{hi} — that gives me a great start, and I'll remember it.")
    print("  Tell me more anytime, or type  :learn.")


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
