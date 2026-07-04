"""Terminal interface — a REPL over the orchestrator. Runnable once the
stubs it touches are implemented."""
from __future__ import annotations


def run_repl(orchestrator, session) -> None:
    print("agi-layer — 'exit' quits | ':scope <name>' switch project | "
          "':good'/':bad' rate last | ':optimize' improve")
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
        if line in (":good", ":bad"):
            orchestrator.feedback.rate(session.session_id, 1.0 if line == ":good" else -1.0)
            print("[feedback recorded]")
            continue
        if line == ":optimize":
            print(f"[optimize] {orchestrator.optimize()}")
            continue
        try:
            reply = orchestrator.handle_turn(line, session)
        except Exception as e:
            print(f"[error] {type(e).__name__}: {e}")
            continue
        print(f"layer> {reply}")
