"""Terminal interface — a REPL over the orchestrator. Runnable once the
stubs it touches are implemented."""
from __future__ import annotations


def run_repl(orchestrator, session) -> None:
    print("agi-layer — type 'exit' to quit, ':scope <name>' to switch project.")
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line in {"exit", "quit"}:
            break
        if not line:
            continue
        if line.startswith(":scope "):
            session.set_scope(line.split(" ", 1)[1].strip() or None)
            print(f"[scope -> {session.active_scope}]")
            continue
        reply = orchestrator.handle_turn(line, session)
        print(f"layer> {reply}")
