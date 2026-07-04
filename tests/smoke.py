"""Offline smoke test for the agi-layer spine.

Runs with zero external services (no API key, no Ollama, no Mem0): it exercises
the real SQLite episodic store, the retrieval pipeline, and a full orchestrator
turn using the offline echo model. Proves the core promise in miniature — write
a turn, recall it later — plus that the whole read->route->assemble->generate->
write loop completes.

Run:  python3 tests/smoke.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.context_builder import ContextBuilder          # noqa: E402
from core.orchestrator import Orchestrator                # noqa: E402
from core.policy import Policy                            # noqa: E402
from core.router import Router                            # noqa: E402
from core.session import Session                          # noqa: E402
from improvement.feedback import Feedback                 # noqa: E402
from improvement.skills import Skills                     # noqa: E402
from memory.episodic import EpisodicStore                 # noqa: E402
from memory.graph import GraphStore                       # noqa: E402
from memory.procedural import ProceduralStore             # noqa: E402
from memory.schema import Turn                            # noqa: E402
from memory.semantic import SemanticStore                 # noqa: E402
from memory.store import MemoryStore                      # noqa: E402
from memory.write_path import WritePipeline               # noqa: E402
from models.frontier import FrontierModel                 # noqa: E402
from models.local import LocalModel                       # noqa: E402
from models.registry import ModelRegistry                 # noqa: E402

PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
_results: list[bool] = []


def check(name: str, cond: bool) -> None:
    _results.append(bool(cond))
    print(f"  [{PASS if cond else FAIL}] {name}")


def build_memory(tmp: str):
    episodic = EpisodicStore(os.path.join(tmp, "episodic.db"))
    semantic = SemanticStore(os.path.join(tmp, "vectors"))   # degrades w/o Mem0
    graph = GraphStore(os.path.join(tmp, "graph"))
    procedural = ProceduralStore(os.path.join(tmp, "episodic.db"))
    write_pipeline = WritePipeline(episodic=episodic, semantic=semantic, graph=graph)
    mem = MemoryStore(
        episodic=episodic, semantic=semantic, graph=graph, procedural=procedural,
        embedder=None, write_pipeline=write_pipeline, consolidator=None,
        reranker=None, write_async=False,
    )
    return mem, episodic, semantic


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="agi-smoke-")
    print(f"agi-layer smoke test  (data: {tmp})\n")

    mem, episodic, semantic = build_memory(tmp)
    print(f"Semantic (Mem0) available: {semantic.available}   "
          f"Episodic FTS5: {episodic._fts}\n")

    # 1) write -> persist -> recall through the real SQLite spine
    print("1) memory: write a fact, recall it later")
    sess = Session(scope="demo")
    sess.add_user("Remember: my dog is named Zephyr and he is a border collie.")
    sess.add_assistant("Got it — Zephyr, a border collie.")
    mem.write(Turn.from_session(sess))

    bundle = mem.retrieve("what is my dog's name?", scope="demo", budget_tokens=2000)
    contents = " ".join(c.content for c in bundle.items).lower()
    check("retrieval returns candidates", len(bundle.items) > 0)
    check("recalls the stored fact (Zephyr)", "zephyr" in contents)
    check("token budget respected", bundle.token_count <= 2000)

    # 2) full orchestrator turn loop with the offline echo model
    print("\n2) orchestrator: full read->route->assemble->generate->write turn")
    registry = ModelRegistry(
        {"models": [{"name": "echo", "adapter": "echo"}], "defaults": {"fallback": "echo"}},
        FrontierModel, LocalModel,
    )
    orch = Orchestrator(
        memory=mem, router=Router(registry, Policy()),
        context_builder=ContextBuilder(), skills=Skills(), feedback=Feedback(),
    )
    sess2 = Session(scope="demo")
    reply = orch.handle_turn("Hello, what do you know about my dog?", sess2)
    check("handle_turn returns a reply", isinstance(reply, str) and len(reply) > 0)
    check("router fell back to echo (no key / Ollama)", "echo" in reply.lower())

    bundle2 = mem.retrieve("dog border collie", scope="demo", budget_tokens=2000)
    check("cross-session recall still finds the fact",
          any("zephyr" in c.content.lower() for c in bundle2.items))

    # 3) episodic is the durable source of truth
    print("\n3) episodic durability")
    rows = list(episodic.iter_since(0))
    check("episodes persisted to SQLite", len(rows) >= 2)

    print()
    if all(_results):
        print(f"All {len(_results)} checks {PASS}")
        return 0
    print(f"{sum(1 for r in _results if not r)}/{len(_results)} checks {FAIL}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
