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
import time

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
from memory.schema import ContextBundle, Entity, Relation, Source, Turn   # noqa: E402
from memory.semantic_native import NativeSemanticStore    # noqa: E402
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
    semantic = NativeSemanticStore(os.path.join(tmp, "vectors"))  # owned vector store
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
    print(f"Semantic backend: native (available={semantic.available})   "
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
    check("router fell back to echo (no key / Ollama)", "offline" in reply.lower())

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

    # 9) background scheduler (APScheduler or stdlib-timer fallback)
    print("\n9) background scheduler")
    from core.scheduler import Scheduler
    hits = {"n": 0}
    sch = Scheduler(lambda: hits.__setitem__("n", hits["n"] + 1), interval_seconds=999)
    backend = sch.start()
    sch.run_now()
    sch.stop()
    check("scheduler.run_now triggers the job", hits["n"] >= 1)
    check("scheduler starts on a backend", backend in ("apscheduler", "timer"))

    # 10) graph auto-population from the write path
    print("\n10) graph population from writes")
    gmem, _gepi, _gsem = build_memory(os.path.join(tmp, "gpop"))
    gsess = Session(scope="proj")
    gsess.add_user("I deploy WhaleTrack using Docker and Fly.")
    gsess.add_assistant("Noted.")
    gmem.write(Turn.from_session(gsess))
    gnb = gmem.graph.neighbors(["WhaleTrack"], scope="proj")
    check("write path auto-populated the graph (co-occurrences)", len(gnb) >= 1)

    # 11) GEPA optimizer (optional DSPy upgrade) import-guards cleanly
    print("\n11) GEPA optimizer")
    from improvement.gepa_optimizer import GEPAOptimizer
    gepa = GEPAOptimizer()
    ok_gepa = True
    if not gepa.available():
        try:
            gepa.evolve_prompt("base", [])
            ok_gepa = False
        except RuntimeError:
            ok_gepa = True
        except Exception:
            ok_gepa = False
    check("GEPA optimizer available or import-guards cleanly", ok_gepa)

    # 12) native semantic memory: vector search + reconcile + supersede + decay
    print("\n12) native semantic memory (owned vector store)")
    from memory.schema import MemoryItem
    ns = NativeSemanticStore(os.path.join(tmp, "nsem"))
    ns.add_turn("My favourite database is Postgres and I love Rust.", "ok", scope="p")
    ns.add_turn("My favourite database is Postgres and I love Rust.", "ok", scope="p")
    check("reconcile dedups near-duplicate facts", ns.count_current("p") == 1)
    hits = ns.search("what database do I like", scope="p", k=5)
    check("native vector search returns VECTOR candidates",
          len(hits) >= 1 and hits[0].source == Source.VECTOR)
    base = ns.search("database", scope="p")[0]
    ns.supersede(base.ref_id, MemoryItem(content="I now prefer SQLite.", scope="p"))
    cur = ns.search("database", scope="p")
    check("supersede writes new + retires old (temporal)",
          any("SQLite" in h.content for h in cur) and ns.count_current("p") == 1)
    ns.upsert(MemoryItem(content="Trivial throwaway.", scope="p",
                         importance=0.01, last_accessed=0.0))
    before = ns.count_current("p")
    ns.decay(half_life_days=30, cold_threshold=0.15)
    check("decay archives cold items", ns.count_current("p") < before)

    # 13) LLM-driven extraction + contradiction -> supersede (scripted stub model)
    print("\n13) LLM extraction + contradiction supersede")
    from memory.extractor import LLMExtractor

    class _StubLLM:
        model_name, is_local = "stub", True

        def available(self):
            return True

        def generate(self, prompt, tools=None):
            sysmsg = prompt[0]["content"] if prompt and isinstance(prompt[0], dict) else ""
            if "CONTRADICTS" in sysmsg:          # judge call
                return "CONTRADICTS"
            if "JSON array" in sysmsg:           # extract call
                return '["I live in Berlin"]'
            return ""

    ns2 = NativeSemanticStore(os.path.join(tmp, "llmsem"), extractor=LLMExtractor(_StubLLM()))
    ns2.upsert(MemoryItem(content="I live in Sofia.", scope="x"))
    ns2.add_turn("(the turn text)", "", scope="x")   # stub extracts "I live in Berlin"
    live = [h.content for h in ns2.search("where do I live", scope="x")]
    check("LLM extraction produced a current fact", ns2.count_current("x") == 1)
    check("contradiction superseded the stale fact",
          any("Berlin" in c for c in live) and not any("Sofia" in c for c in live))

    # 14) typed relation extraction into the graph
    print("\n14) typed relations")

    class _RelLLM:
        model_name, is_local = "rel", True

        def available(self):
            return True

        def generate(self, prompt, tools=None):
            sysmsg = prompt[0]["content"] if prompt and isinstance(prompt[0], dict) else ""
            if "triples" in sysmsg:
                return '[["You","works_on","WhaleTrack"],["WhaleTrack","uses","Docker"]]'
            return "[]"

    tg = GraphStore(os.path.join(tmp, "tgraph"))
    wp = WritePipeline(episodic=None, semantic=object(), graph=tg,
                       extractor=LLMExtractor(_RelLLM()))
    wp._update_graph(Turn(user_input="I work on WhaleTrack with Docker.",
                          assistant_reply="", scope="w"))
    check("typed relations extracted into the graph",
          any("works_on" in c.content for c in tg.neighbors(["You"], scope="w")))

    # 15) skill self-authoring (governed, fail-closed)
    print("\n15) skill self-authoring")
    from governance.audit import Audit
    from governance.guardrails import Guardrails

    class _SkillLLM:
        model_name, is_local = "sk", True

        def available(self):
            return True

        def generate(self, prompt, tools=None):
            return "```python\ndef skill(payload):\n    return sum(payload.get('nums', []))\n```"

    denied = Skills(model=_SkillLLM(), registry_dir=os.path.join(tmp, "sk1"),
                    guardrails=Guardrails()).author("sum a list of numbers")
    check("skill authoring denied by default (fail closed)",
          denied["status"] == "denied-by-governance")
    aud = Audit(os.path.join(tmp, "sk_audit.jsonl"))
    sk = Skills(model=_SkillLLM(), registry_dir=os.path.join(tmp, "sk2"),
                guardrails=Guardrails(allowed_actions={"skill_author"}), audit=aud)
    res = sk.author("sum a list of numbers", test_input={"nums": [1, 2, 3]})
    check("skill authored + sandbox-tested + registered", res["status"] == "registered")
    check("authored skill is registered + runnable",
          sk.get(res["name"]) is not None and sk.get(res["name"])({"nums": [2, 3]}) == 5)
    check("skill authoring audited", len(aud.tail()) >= 1)

    # 16) memory seeding — bootstrap what we know about the user
    print("\n16) memory seeding")
    from memory.seed import seed_memory
    smem, _s1, _s2 = build_memory(os.path.join(tmp, "seed"))
    seeded = seed_memory(smem)
    check("seeding wrote facts + relations",
          seeded["facts"] >= 3 and seeded["relations"] >= 3)
    got = smem.retrieve("what am I building?", scope=None, budget_tokens=2000)
    check("seeded facts are retrievable", any("agi-layer" in c.content for c in got.items))
    check("seeded relations landed in the graph",
          any("works_on" in c.content for c in smem.graph.neighbors(["You"], scope=None)))

    # 17) scope + privacy regressions (Phase 9 review fixes)
    print("\n17) scope + privacy")
    pmem, _pe, psem = build_memory(os.path.join(tmp, "priv"))
    psem.upsert(MemoryItem(content="Your name is Yulian.", scope=None, importance=0.8))
    hs = Session(scope="health-private")
    hs.add_user("My blood pressure is 130 over 85 lately.")
    hs.add_assistant("noted")
    pmem.write(Turn.from_session(hs))
    # global/identity facts surface INSIDE a project scope (the S1 fix)
    inproj = pmem.retrieve("what is my name", scope="whaletrack", budget_tokens=2000)
    check("global facts retrievable inside a project scope",
          any("Yulian" in c.content for c in inproj.items))
    # sensitive-scope memory is withheld from an external model (the M1 fix)...
    ext = pmem.retrieve("blood pressure", scope="health-private",
                        budget_tokens=2000, for_external=True)
    check("sensitive memory withheld from external models",
          not any("blood" in c.content.lower() for c in ext.items))
    # ...but still available to an on-box model
    loc = pmem.retrieve("blood pressure", scope="health-private",
                        budget_tokens=2000, for_external=False)
    check("sensitive memory still available on-box",
          any("blood" in c.content.lower() for c in loc.items))
    # re-seeding is idempotent (deterministic ids)
    smem2, _q1, _q2 = build_memory(os.path.join(tmp, "seed2"))
    from memory.seed import seed_memory as _seed
    _seed(smem2); _seed(smem2)
    check("re-seeding is idempotent (no duplicates)", smem2.semantic.count_current(None) == 7)

    # 18) ingestion + memory control + proactive (Phase 10)
    print("\n18) ingestion + memory control + proactive")
    from core.proactive import Proactive
    from memory.ingest import ingest_path
    imem, _im1, _im2 = build_memory(os.path.join(tmp, "ing"))
    doc = os.path.join(tmp, "notes.md")
    with open(doc, "w", encoding="utf-8") as f:
        f.write("WhaleTrack uses Postgres and Docker for deploys.\n"
                "The Ocado dashboard is due Friday.\n")
    rep = ingest_path(imem, doc, scope="work")
    check("ingestion learned from a file", rep["files"] == 1 and rep["facts"] >= 1)
    got = imem.retrieve("what does WhaleTrack use", scope="work", budget_tokens=1500)
    check("ingested content is retrievable",
          any("postgres" in c.content.lower() for c in got.items))

    imem.remember("My cat is named Milo.", scope="work")
    check("remember + provenance", any("Milo" in p["content"]
          for p in imem.provenance("cat", scope="work")))
    check("forget archives matching memory",
          imem.forget("cat", scope="work") >= 1 and
          not any("Milo" in p["content"] for p in imem.provenance("cat", scope="work")))

    imem.remember("I live in Sofia.", scope="work")
    imem.correct("where I live", "I live in Berlin now.", scope="work")
    prov_live = imem.provenance("live", scope="work")
    check("correct supersedes the old fact",
          any("Berlin" in p["content"] for p in prov_live) and
          not any("Sofia" in p["content"] for p in prov_live))

    pro = Proactive(imem)
    check("proactive detects profile gaps", len(pro.gaps(scope="work")) >= 1)
    slot = pro.next_question(scope="work")
    imem.remember(pro.fact_from_answer(slot, "Yulian"), scope="work")
    check("active-learning answer is stored",
          any("Yulian" in p["content"] for p in imem.provenance(slot["key"], scope="work")))

    # 19) agent execution layer — governed tool use + routines (Phase 11)
    print("\n19) agent tools + routines")
    from core.agent import Agent
    from core.routines import Routines
    from core.tools import build_default_tools
    from governance.audit import Audit as _Audit

    class _ScriptRouter:
        """A router whose model emits a scripted sequence of tool-call / final
        JSON replies — exercises the agent loop with zero external services."""

        def __init__(self, scripts):
            self._scripts = list(scripts)
            self.registry = None

        def pick(self, query, ctx, scope=None):
            return object()

        def generate(self, model, prompt, tools=None):
            reply = self._scripts.pop(0) if self._scripts else '{"final": "done"}'
            return model, reply

    a_tools = build_default_tools(None)
    a_audit = _Audit(os.path.join(tmp, "agent_audit.jsonl"))
    # calc a value across two steps, then answer with it
    agent = Agent(_ScriptRouter(['{"tool": "calc", "args": {"expression": "6*7"}}',
                                 '{"final": "The answer is 42."}']),
                  a_tools, audit=a_audit)
    ares = agent.run("what is 6 times 7", scope=None, confirm=lambda *_: True)
    check("agent calls a tool then answers",
          ares["answer"] == "The answer is 42." and
          any(s["tool"] == "calc" and str(s["result"]) == "42" for s in ares["steps"]))

    # a gated tool (run_shell) is denied fail-closed without confirmation
    agent_b = Agent(_ScriptRouter(['{"tool": "run_shell", "args": {"command": "echo hi"}}',
                                   '{"final": "could not run it"}']),
                    a_tools, audit=a_audit)
    bres = agent_b.run("run echo hi", scope=None, confirm=None)
    check("gated tool denied without confirmation",
          any(s["tool"] == "run_shell" and "denied" in str(s["result"])
              for s in bres["steps"]))
    check("agent tool calls are audited", len(a_audit.tail()) >= 2)

    # routines: add, list, run unattended, and persist across a restart
    agent_c = Agent(_ScriptRouter(['{"tool": "calc", "args": {"expression": "2+2"}}',
                                   '{"final": "4"}']),
                    a_tools, audit=a_audit)
    routines = Routines(os.path.join(tmp, "routines.json"), agent_c)
    routines.add("mathcheck", "compute 2+2", scope=None)
    check("routine saved + listed", "mathcheck" in routines.list())
    rres = routines.run("mathcheck")
    check("routine runs unattended", rres["status"] == "ran" and rres["answer"] == "4")
    routines2 = Routines(os.path.join(tmp, "routines.json"), agent_c)
    check("routines persist across restart", "mathcheck" in routines2.list())

    # 20) web/browser tools + scheduled routines (Phase 12)
    print("\n20) web tools + scheduled routines")
    from core.tools import (_html_to_text, _parse_ddg, _web_fetch,
                            build_default_tools as _bdt)
    web_names = _bdt(None, allow_web=True).names()
    check("web tools registered when allowed",
          "web_search" in web_names and "web_fetch" in web_names)
    check("web tools omitted when disallowed",
          "web_fetch" not in _bdt(None, allow_web=False).names())
    # SSRF guard: private/loopback + non-http schemes are blocked (no network).
    check("web_fetch blocks loopback (SSRF guard)",
          "blocked" in _web_fetch({"url": "http://127.0.0.1:80/admin"}))
    check("web_fetch blocks non-http schemes",
          "blocked" in _web_fetch({"url": "file:///etc/passwd"}))
    check("html is reduced to readable text",
          _html_to_text("<p>Hello <b>there</b></p><script>x=1</script>") == "Hello there")
    ddg = _parse_ddg('<a class="result__a" href="//duckduckgo.com/l/'
                     '?uddg=https%3A%2F%2Fexample.com%2Fa&rut=z">Example A</a>')
    check("search results parse to (title, url)",
          ddg == [("Example A", "https://example.com/a")])

    # interval scheduling: due only after next_run, then advances
    sagent = Agent(_ScriptRouter(['{"final": "ok"}']), a_tools)
    sr = Routines(os.path.join(tmp, "sched.json"), sagent)
    sr.add("tick", "return ok")
    sr.schedule("tick", every_minutes=30, now=1000.0)   # next_run = 2800
    check("scheduled routine not due before its time", not sr.run_due(now=2000.0))
    fired = sr.run_due(now=3000.0)                       # due -> fires
    check("scheduled routine fires when due",
          any(f["name"] == "tick" and f["answer"] == "ok" for f in fired))
    check("next run advances after firing", sr.list()["tick"]["next_run"] == 4800.0)
    sr2 = Routines(os.path.join(tmp, "sched.json"), sagent)
    check("schedule persists across restart", sr2.list()["tick"].get("every_minutes") == 30)

    # daily 'at HH:MM' scheduling: fires once per day at/after the time
    dagent = Agent(_ScriptRouter([]), a_tools)  # scripts exhausted -> final "done"
    dr = Routines(os.path.join(tmp, "daily.json"), dagent)
    dr.add("brief", "daily briefing")
    base = 1_700_000_000.0
    lt = time.localtime(base)
    dr.schedule("brief", at=f"{lt.tm_hour:02d}:{lt.tm_min:02d}")
    check("daily routine fires at its time",
          any(f["name"] == "brief" for f in dr.run_due(now=base)))
    check("daily routine doesn't refire the same day",
          not any(f["name"] == "brief" for f in dr.run_due(now=base + 60)))

    # 21) Playwright browser tool + prebuilt starter routines (Phase 13)
    print("\n21) browser tool + starter routines")
    from core.tools import _browse
    from core.routines import describe_schedule
    from core.starter_routines import install_starters
    check("browse tool registered when web is allowed",
          "browse" in _bdt(None, allow_web=True).names())
    check("browse tool omitted when web is disallowed",
          "browse" not in _bdt(None, allow_web=False).names())
    # SSRF guard applies to the browser too (checked before any launch/import).
    check("browse blocks loopback (SSRF guard)",
          "blocked" in _browse({"url": "http://127.0.0.1/"}))

    stagent = Agent(_ScriptRouter([]), a_tools)
    strt = Routines(os.path.join(tmp, "starters.json"), stagent)
    added = install_starters(strt)
    check("starter routines install (idempotent)",
          len(added) >= 2 and install_starters(strt) == [])
    check("a named starter (morning) is present with a task",
          bool(strt.list().get("morning", {}).get("task")))
    check("starters are unscheduled by default (no background work)",
          all(not describe_schedule(it) for it in strt.list().values()))

    # 22) connectors — git / calendar / email (Phase 14, real reads)
    print("\n22) connectors: git / calendar / email")
    from core import connectors as conn
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    gl = conn.git_log(repo_root, 3)
    check("git connector reads recent commits",
          not gl.startswith("(") and len(gl.splitlines()) >= 1)
    check("git connector reports status", "##" in conn.git_status(repo_root))

    ics = os.path.join(tmp, "cal.ics")
    soon = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(time.time() + 3600))
    old = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(time.time() - 2 * 86400))
    with open(ics, "w", encoding="utf-8") as f:
        f.write("BEGIN:VCALENDAR\n"
                f"BEGIN:VEVENT\nSUMMARY:Dentist\nDTSTART:{soon}\nEND:VEVENT\n"
                f"BEGIN:VEVENT\nSUMMARY:OldMeeting\nDTSTART:{old}\nEND:VEVENT\n"
                "END:VCALENDAR\n")
    cal_out = conn.calendar_upcoming(ics, days=7)
    check("calendar connector lists upcoming, excludes past",
          "Dentist" in cal_out and "OldMeeting" not in cal_out)

    mbx = os.path.join(tmp, "mail.mbox")
    with open(mbx, "w", encoding="utf-8") as f:
        f.write("From alice@example.com Mon Jan  1 00:00:00 2024\n"
                "From: alice@example.com\nSubject: Hello\n"
                "Date: Mon, 01 Jan 2024 00:00:00 +0000\n\nHi there\n\n"
                "From bob@example.com Tue Jan  2 00:00:00 2024\n"
                "From: bob@example.com\nSubject: Invoice\n"
                "Date: Tue, 02 Jan 2024 00:00:00 +0000\n\nPlease pay\n\n")
    em = conn.email_recent(mbx, 5)
    check("email connector reads a local mailbox", "Hello" in em and "Invoice" in em)

    stt = conn.connector_status({"git_repo": repo_root, "calendar_file": ics, "mailbox_file": mbx})
    check("connector status reports configured connectors",
          stt["git"].startswith("ok") and stt["calendar"].startswith("ok")
          and stt["email"].startswith("ok"))

    ctools = _bdt(None, allow_web=False, connectors={"git_repo": repo_root})
    check("connector tools registered",
          all(t in ctools.names() for t in
              ("git_log", "git_status", "calendar_upcoming", "email_recent")))
    cagent = Agent(_ScriptRouter(['{"tool": "git_log", "args": {"n": 2}}',
                                  '{"final": "done"}']), ctools)
    cres = cagent.run("show recent commits")
    check("agent can call a connector tool",
          any(s["tool"] == "git_log" and not str(s["result"]).startswith("(error")
              for s in cres["steps"]))

    # 23) interactive browsing — action DSL + gating (Phase 14)
    print("\n23) interactive browsing")
    from core.tools import _browse_do, _parse_actions
    acts = _parse_actions("goto https://x.test\nfill #user = alice\n"
                          "click text=Login\nwait 500\nread .result\n# a comment")
    check("action DSL parses verbs/targets/values",
          [a["verb"] for a in acts] == ["goto", "fill", "click", "wait", "read"]
          and acts[1]["target"] == "#user" and acts[1]["value"] == "alice")
    check("interactive browse keeps the SSRF guard",
          "blocked" in _browse_do({"url": "http://127.0.0.1/", "steps": "read"}))
    check("interactive browse degrades without Playwright",
          "Playwright" in _browse_do({"url": "http://example.invalid/", "steps": "read"}))
    # acting on a page is GATED -> denied in an unattended run (fail-closed)
    web_tools = _bdt(None, allow_web=True)
    check("browse_do is a gated tool", not web_tools.get("browse_do").unattended)
    gagent = Agent(_ScriptRouter(
        ['{"tool": "browse_do", "args": {"url": "https://x.test", "steps": "click text=Buy"}}',
         '{"final": "stopped"}']), web_tools, audit=a_audit)
    gres = gagent.run("buy something", confirm=None)
    check("interactive browse denied without confirmation",
          any(s["tool"] == "browse_do" and "denied" in str(s["result"])
              for s in gres["steps"]))

    print()
    if all(_results):
        print(f"All {len(_results)} checks {PASS}")
        return 0
    print(f"{sum(1 for r in _results if not r)}/{len(_results)} checks {FAIL}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
