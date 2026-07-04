"""Offline smoke test for the agi-layer spine + Phase 2 additions.

Runs with zero external services (no API key, no Ollama, no Mem0). Covers:
  1-3  memory write->recall, full turn loop, episodic durability (Phase 1)
  4    scope-aware privacy routing (sensitive scope never leaves the box)
  5    knowledge-graph multi-hop traversal
  6    consolidation "sleep" pass + watermark

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
from memory.consolidation import Consolidator             # noqa: E402
from memory.episodic import EpisodicStore                 # noqa: E402
from memory.graph import GraphStore                       # noqa: E402
from memory.procedural import ProceduralStore             # noqa: E402
from memory.schema import ContextBundle, Entity, Relation, Turn   # noqa: E402
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
    os.makedirs(tmp, exist_ok=True)
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

    mem, episodic, semantic = build_memory(os.path.join(tmp, "main"))
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

    # 4) scope-aware privacy routing
    print("\n4) scope-aware privacy routing")
    reg = ModelRegistry(
        {"models": [{"name": "echo", "adapter": "echo"}],
         "defaults": {"general": "cloud", "hard_reasoning": "cloud",
                      "private": "qwen-local", "fallback": "echo"}},
        FrontierModel, LocalModel)

    class _Cloud:  # a reachable external model that sensitive scopes must avoid
        model_name, is_local = "cloud", False

        def available(self):
            return True

        def generate(self, prompt, tools=None):
            return "cloud"

    reg._adapters["cloud"] = _Cloud()
    reg._meta["cloud"] = {"name": "cloud"}
    router = Router(reg, Policy())
    empty = ContextBundle()
    m_priv = router.pick("show my health notes", empty, scope="health-private")
    m_gen = router.pick("hello there", empty, scope="work")
    check("sensitive scope stays on-box (never cloud)",
          getattr(m_priv, "is_local", False) and m_priv.model_name != "cloud")
    check("non-sensitive scope can use the cloud model", m_gen.model_name == "cloud")

    # 5) knowledge graph — multi-hop traversal
    print("\n5) knowledge graph — multi-hop")
    g = GraphStore(os.path.join(tmp, "graph_test"))
    wt = Entity(name="WhaleTrack", type="project", scope="demo")
    dk = Entity(name="Docker", type="tool", scope="demo")
    g.upsert_entity(wt)
    g.upsert_entity(dk)
    g.upsert_relation(Relation(src=wt.id, dst=dk.id, type="uses", scope="demo"))
    nb = g.neighbors(["WhaleTrack"], scope="demo")
    check("graph traversal returns the connected fact (Docker)",
          any("Docker" in c.content for c in nb))

    # 6) consolidation — the sleep pass + watermark
    print("\n6) consolidation — the sleep pass")
    con = Consolidator(episodic=episodic, semantic=semantic,
                       graph=GraphStore(os.path.join(tmp, "cgraph")))
    rep = con.run()
    check("consolidation processed new episodes", rep["new_episodes"] >= 2)
    check("consolidation produced a summary", rep["summaries"] >= 1)
    rep2 = con.run()
    check("watermark advances (no re-processing)", rep2["new_episodes"] == 0)

    # 7) governed self-improvement loop
    print("\n7) self-improvement + governance")
    from governance.audit import Audit
    from governance.guardrails import Guardrails
    from governance.versioning import Versioning
    from improvement.optimizer import Optimizer
    fb = Feedback()
    for _ in range(6):  # synthetic feedback: one model clearly better
        fb.signals.append({"session_id": "s", "model": "good-model", "score": 0.9})
        fb.signals.append({"session_id": "s", "model": "bad-model", "score": 0.1})
    pol = Policy()
    opt = Optimizer()
    proposal = opt.propose(pol, fb.recent())
    check("optimizer proposes routing to the best model",
          proposal is not None and proposal.routing_rules.get("general") == "good-model")
    aud = Audit(os.path.join(tmp, "audit.jsonl"))
    ver = Versioning(os.path.join(tmp, "versions"))
    approved = opt.apply(pol, proposal, guardrails=Guardrails(), versioning=ver, audit=aud)
    check("governance approves a bounded update", approved is not None)
    check("audit recorded the change", len(aud.tail()) >= 1)
    check("versioning snapshotted (rollback available)", len(ver.list()) >= 1)
    over = Policy(routing_rules={c: c for c in "abcdef"})
    denied = opt.apply(pol, over, guardrails=Guardrails(max_policy_changes=2),
                       versioning=ver, audit=aud)
    check("guardrails deny an over-ceiling update", denied is None)

    # 8) bridge interfaces build or import-guard cleanly
    print("\n8) bridge interfaces (MCP / HTTP)")
    from interfaces.api import build_app
    from interfaces.mcp import build_mcp_server

    def _builds_or_guards(fn):
        try:
            return fn() is not None      # dep present -> built
        except RuntimeError:
            return True                  # dep absent -> clean guard
        except Exception:
            return False                 # anything else is a real bug

    check("MCP bridge builds or import-guards cleanly",
          _builds_or_guards(lambda: build_mcp_server(mem, orch)))
    check("HTTP API builds or import-guards cleanly",
          _builds_or_guards(lambda: build_app(orch)))

    print()
    if all(_results):
        print(f"All {len(_results)} checks {PASS}")
        return 0
    print(f"{sum(1 for r in _results if not r)}/{len(_results)} checks {FAIL}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
