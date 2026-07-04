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

_COLOR = sys.stdout.isatty() and os.name != "nt"   # plain text on Windows consoles
PASS, FAIL = (("\033[32mPASS\033[0m", "\033[31mFAIL\033[0m") if _COLOR
              else ("PASS", "FAIL"))
_results: list[bool] = []


def check(name: str, cond: bool) -> None:
    _results.append(bool(cond))
    print(f"  [{PASS if cond else FAIL}] {name}")


def _enc_roundtrip(bk, src: str, workdir: str) -> bool:
    """Encrypt src then decrypt it back and confirm the bytes match. If
    `cryptography` isn't installed, encrypt returns None -> the optional feature
    is simply absent, which counts as a pass."""
    os.makedirs(workdir, exist_ok=True)
    enc = bk.encrypt_file(src, "pw123")
    if enc is None:
        return True
    out = os.path.join(workdir, "dec.tar.gz")
    if not bk.decrypt_file(enc, "pw123", out):
        return False
    with open(src, "rb") as a, open(out, "rb") as b:
        return a.read() == b.read()


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
    check("phone briefing + end-of-day recap starters install",
          "phone_briefing" in strt.list() and "eod_recap" in strt.list())
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

    # 24) networked connectors — GitHub / IMAP / calendar-URL (Phase 15)
    print("\n24) networked connectors")
    gh_json = ('[{"sha":"abcdef1234","commit":{"message":"Fix bug\\nmore",'
               '"author":{"name":"Al"}}}]')
    check("github commit JSON parses",
          conn._parse_github_commits(gh_json) == [("abcdef1", "Fix bug", "Al")])
    check("github_recent guards a bad repo id", conn.github_recent("noslash").startswith("("))
    check("calendar over a URL keeps the SSRF guard",
          "blocked" in conn.calendar_upcoming("http://127.0.0.1/cal.ics"))
    check("imap header formatting", conn._fmt_headers("a@b", "Hi", "Mon") == "Mon · a@b — Hi")
    check("imap connector is config-gated", "not configured" in conn.imap_recent("", "", ""))
    stt2 = conn.connector_status({"git_repo": repo_root, "github_repo": "octocat/Hello-World",
                                  "imap_host": "imap.x", "imap_user": "u", "imap_password": "p"})
    check("status reports networked connectors",
          stt2["github"].startswith("ok") and stt2["imap"].startswith("ok"))
    ntools = _bdt(None, allow_web=False,
                  connectors={"git_repo": repo_root, "github_repo": "a/b"})
    itools = _bdt(None, allow_web=False,
                  connectors={"imap_host": "h", "imap_user": "u", "imap_password": "p"})
    check("github tool registered; imap tool only when configured",
          "github_recent" in ntools.names() and "email_imap" in itools.names()
          and "email_imap" not in ntools.names())

    # 25) perceive-act browsing loop (Phase 15)
    print("\n25) perceive-act browsing loop")
    from core.browser_agent import BrowserPilot

    class _FakeSession:
        def __init__(self, obs):
            self._obs, self.acted = list(obs), []

        def observe(self):
            return self._obs.pop(0) if self._obs else "URL: end\nTEXT: end\nELEMENTS:"

        def act(self, action):
            self.acted.append(action)
            return "ok"

        def close(self):
            pass

    fake = _FakeSession(["obs1", "obs2", "obs3"])
    pilot = BrowserPilot(_ScriptRouter(['{"action": "click", "target": "text=Login"}',
                                        '{"action": "fill", "target": "#u", "value": "al"}',
                                        '{"done": "logged in"}']))
    pres = pilot.run("https://x.test", "log in", session=fake)
    check("perceive-act runs actions then finishes",
          pres["answer"] == "logged in" and len(pres["steps"]) == 2
          and fake.acted[0]["action"] == "click" and fake.acted[1]["value"] == "al")
    check("perceive-act blocks a private URL",
          "blocked" in BrowserPilot(_ScriptRouter([])).run("http://127.0.0.1/", "x")["answer"])
    check("perceive-act needs Playwright for a real page",
          "Playwright" in BrowserPilot(_ScriptRouter([])).run("http://example.invalid/", "x")["answer"])
    bp = BrowserPilot(_ScriptRouter([]))
    check("browse_agent registered and gated",
          _bdt(None, allow_web=True, browser_pilot=bp).get("browse_agent") is not None
          and not _bdt(None, allow_web=True, browser_pilot=bp).get("browse_agent").unattended)
    check("browse_agent omitted without a pilot",
          _bdt(None, allow_web=True).get("browse_agent") is None)

    # 26) connector write actions — calendar / github / email, all gated (Phase 16)
    print("\n26) connector write actions")
    wics = os.path.join(tmp, "write.ics")
    when = time.strftime("%Y-%m-%d %H:%M", time.gmtime(time.time() + 3600))
    check("calendar_add_event writes an event",
          conn.calendar_add_event(wics, "Standup", when, duration_min=30).startswith("added"))
    check("added event is readable back", "Standup" in conn.calendar_upcoming(wics, days=7))
    blk = conn._ics_event_block("u", "T", 0, 60)
    check("event block is well-formed", "BEGIN:VEVENT" in blk and "SUMMARY:T" in blk)
    check("calendar write refuses a URL target",
          "URL" in conn.calendar_add_event("https://x/cal.ics", "T", when))

    url, headers, data = conn._build_github_issue_request("o/r", "Bug", "desc", "tok")
    check("github issue request is a correct POST payload",
          url.endswith("/repos/o/r/issues") and headers.get("Authorization") == "Bearer tok"
          and b'"title": "Bug"' in data)
    check("create-issue needs a token",
          "github_token" in conn.github_create_issue("o/r", "T", "", token=None))
    check("issues/PRs parse from JSON",
          conn._parse_github_items('[{"number":7,"title":"X","user":{"login":"al"}}]')
          == [(7, "X", "al")])
    check("issue list skips PR entries",
          conn._parse_github_items('[{"number":7,"title":"X","pull_request":{}}]',
                                   issues_only=True) == [])

    emsg = conn._build_email("me@x", "you@y", "Hi", "body")
    check("email MIME builds correct headers + body",
          emsg["From"] == "me@x" and emsg["To"] == "you@y" and emsg["Subject"] == "Hi"
          and emsg.get_payload(decode=True) == b"body")
    check("smtp send is config-gated",
          "not configured" in conn.smtp_send("", "", "", "to", "s", "b"))

    wtools = _bdt(None, allow_web=False, connectors={
        "github_repo": "a/b", "calendar_file": wics,
        "smtp_host": "h", "smtp_user": "u", "smtp_password": "p"})
    specs = {s["name"]: s for s in wtools.specs()}
    check("read connectors are unattended",
          specs["github_issues"]["unattended"] and specs["github_prs"]["unattended"])
    check("write connectors are gated",
          not specs["calendar_add_event"]["unattended"]
          and not specs["github_create_issue"]["unattended"]
          and not specs["email_send"]["unattended"])
    check("email_send present only when smtp configured",
          "email_send" not in _bdt(None, allow_web=False,
                                   connectors={"github_repo": "a/b"}).names())
    wagent = Agent(_ScriptRouter(
        ['{"tool": "calendar_add_event", "args": {"title": "X", "start": "2030-01-01 09:00"}}',
         '{"final": "no"}']), wtools)
    wres = wagent.run("add an event", confirm=None)
    check("write connector denied without confirmation",
          any(s["tool"] == "calendar_add_event" and "denied" in str(s["result"])
              for s in wres["steps"]))

    # 27) richer browser perception — accessibility + vision plumbing (Phase 16)
    print("\n27) richer browser perception")
    from core.browser_agent import (BrowserPilot as _BP, _build_messages,
                                    _flatten_ax, _format_observation)
    ax = {"role": "WebArea", "name": "Home", "children": [
        {"role": "button", "name": "Login", "children": []},
        {"role": "generic", "name": "", "children": [
            {"role": "textbox", "name": "Email"}]}]}
    flat = _flatten_ax(ax)
    check("accessibility tree flattens to role/name lines",
          'button "Login"' in flat and 'textbox "Email"' in flat
          and not any("generic" in x for x in flat))
    obs = _format_observation("http://x", "hello", ["A button Login"], flat)
    check("observation includes url, accessibility, elements",
          "URL: http://x" in obs and "ACCESSIBILITY" in obs and "ELEMENTS" in obs)
    tmsgs = _build_messages("goal", "obs", [], "SHOT", supports_vision=False)
    vmsgs = _build_messages("goal", "obs", [], "SHOT", supports_vision=True)
    check("non-vision model gets text-only messages", isinstance(tmsgs[1]["content"], str))
    check("vision model gets a multimodal message with the image",
          isinstance(vmsgs[1]["content"], list)
          and any(p.get("type") == "image_url"
                  and str(p.get("image_url", {}).get("url", "")).startswith("data:image/png;base64,")
                  for p in vmsgs[1]["content"]))

    class _ShotSession:
        def __init__(self):
            self.shots = 0

        def observe(self):
            return "URL: x\nTEXT: t"

        def screenshot(self):
            self.shots += 1
            return "B64"

        def act(self, a):
            return "ok"

        def close(self):
            pass

    class _VisionRouter(_ScriptRouter):
        class _M:
            supports_vision = True

        def pick(self, q, c, scope=None):
            return _VisionRouter._M()

    ss = _ShotSession()
    r1 = _BP(_ScriptRouter(['{"done": "ok"}'])).run("https://x.test", "g", session=ss)
    check("pilot skips screenshots for a non-vision model", r1["answer"] == "ok" and ss.shots == 0)
    ss2 = _ShotSession()
    _BP(_VisionRouter(['{"done": "ok"}'])).run("https://x.test", "g", session=ss2)
    check("pilot captures a screenshot for a vision model", ss2.shots >= 1)

    # 28) Phase 16 adversarial-review hardening
    print("\n28) review hardening (SSRF, calendar, github, coverage)")
    from core.tools import _GuardedRedirect, _do_action

    class _FakePage:
        def __init__(self):
            self.went = []

        def goto(self, url, **k):
            self.went.append(url)

    fp = _FakePage()
    blocked = False
    try:
        _do_action(fp, {"verb": "goto", "target": "http://169.254.169.254/", "value": ""}, [])
    except Exception:
        blocked = True
    check("in-session goto blocks private/metadata targets", blocked and fp.went == [])
    fp2 = _FakePage()
    _do_action(fp2, {"verb": "goto", "target": "https://example.com/", "value": ""}, [])
    check("in-session goto allows public targets", fp2.went == ["https://example.com/"])
    rblocked = False
    try:
        _GuardedRedirect().redirect_request(None, None, 302, "m", {}, "http://127.0.0.1/")
    except Exception:
        rblocked = True
    check("a redirect to a private host is blocked", rblocked)

    check("github page size clamps to <=100",
          conn._gh_page_size(500) == 100 and conn._gh_page_size(5) == 5)
    check("issue filter keeps real (non-PR) issues",
          conn._parse_github_items(
              '[{"number":5,"title":"real","user":{"login":"me"}},'
              '{"number":7,"title":"pr","pull_request":{"url":"x"}}]',
              issues_only=True) == [(5, "real", "me")])

    cr_ics = os.path.join(tmp, "cr.ics")
    conn.calendar_add_event(cr_ics, "Sync\r\nRoom", when)
    check("carriage-return title round-trips without data loss",
          "Sync Room" in conn.calendar_upcoming(cr_ics, days=7))
    with open(cr_ics, encoding="utf-8", newline="") as f:   # newline="" -> no CRLF translation
        raw = f.read()
    check("written calendar has a VCALENDAR envelope + CRLF endings",
          "BEGIN:VCALENDAR" in raw and "END:VCALENDAR" in raw and "\r\n" in raw)
    empty_ics = os.path.join(tmp, "empty.ics")
    open(empty_ics, "w").close()
    conn.calendar_add_event(empty_ics, "Solo", when)
    with open(empty_ics, encoding="utf-8") as f:
        eraw = f.read()
    check("event added to an empty file gets a VCALENDAR wrapper",
          "BEGIN:VCALENDAR" in eraw and "END:VCALENDAR" in eraw and "Solo" in eraw)
    again = conn.calendar_add_event(empty_ics, "Solo", when)
    with open(empty_ics, encoding="utf-8") as f:
        final = f.read()
    check("calendar add is idempotent (no duplicate event)",
          "already" in again and final.count("BEGIN:VEVENT") == 1)

    big = {"role": "list", "name": "L",
           "children": [{"role": "button", "name": str(i)} for i in range(100)]}
    check("flatten_ax respects its node limit", len(_flatten_ax(big, limit=10)) == 10)

    # 29) natural-language auto-routing to the agent (Phase 17)
    print("\n29) natural-language auto-routing")

    def _orch(router, tools, agent, tag):
        m, _e, _s = build_memory(os.path.join(tmp, "nl_" + tag))
        o = Orchestrator(memory=m, router=router, context_builder=ContextBuilder(),
                         skills=Skills(), feedback=Feedback())
        o.tools, o.agent = tools, agent
        return o

    # capable model: plain language -> the agent picks a tool, then answers in prose
    cap_tools = _bdt(None, allow_web=False, connectors={"git_repo": repo_root})
    cap_router = _ScriptRouter(['{"tool": "git_log", "args": {"n": 1}}',
                               "Here's your latest commit."])
    oc = _orch(cap_router, cap_tools, Agent(cap_router, cap_tools), "cap")
    rc = oc.handle_turn("show me my latest commit", Session(), confirm=lambda *_: True)
    check("plain language triggers a tool via the agent",
          any(s["tool"] == "git_log" for s in oc.last_steps) and "commit" in rc.lower())

    # a plain question stays conversational — no tool call
    chat_router = _ScriptRouter(["Your dog is a border collie named Zephyr."])
    och = _orch(chat_router, _bdt(None, allow_web=False),
                Agent(chat_router, _bdt(None, allow_web=False)), "chat")
    rq = och.handle_turn("what kind of dog do I have?", Session(), confirm=None)
    check("a plain question answers conversationally (no tool)",
          "border collie" in rq.lower() and och.last_steps == [])

    # gated tool in a conversational turn is denied without confirmation
    g_tools = _bdt(None, allow_web=False,
                   connectors={"calendar_file": os.path.join(tmp, "nl.ics")})
    g_router = _ScriptRouter(
        ['{"tool": "calendar_add_event", "args": {"title": "X", "start": "2030-01-01 09:00"}}',
         "I need your confirmation to add that."])
    og = _orch(g_router, g_tools, Agent(g_router, g_tools), "gate")
    og.handle_turn("put X on my calendar", Session(), confirm=None)
    check("gated tool denied in a conversational turn without confirm",
          any(s["tool"] == "calendar_add_event" and "denied" in str(s["result"])
              for s in og.last_steps))

    # offline echo model degrades to the plain generate path (no agent routing)
    class _EchoRouter(_ScriptRouter):
        class _E:
            model_name, is_local = "echo", True

            def generate(self, prompt, tools=None):
                return "echo-reply"

        def pick(self, q, c, scope=None):
            return _EchoRouter._E()

        def generate(self, model, prompt, tools=None):
            return model, model.generate(prompt, tools=tools)

    oe = _orch(_EchoRouter([]), _bdt(None, allow_web=False),
               Agent(_EchoRouter([]), _bdt(None, allow_web=False)), "echo")
    re_ = oe.handle_turn("hello", Session(), confirm=None)
    check("offline echo uses the plain path (no agent routing)",
          re_ == "echo-reply" and oe.last_steps == [])

    # 30) identity (Myro) + first-boot onboarding (Phase 18)
    print("\n30) identity + onboarding")
    from core.onboarding import Onboarding
    ob = Onboarding(os.path.join(tmp, "onb.json"))
    qs = ob.questions()
    check("onboarding asks 10-15 questions", 10 <= len(qs) <= 15)
    check("each question has key / prompt / fact template",
          all(q.get("key") and q.get("q") and "{a}" in q.get("fact", "") for q in qs))
    check("skip and stop answers are recognized",
          ob.is_skip("") and ob.is_skip("skip") and ob.is_stop("stop")
          and not ob.is_stop("berlin"))
    omem, _oe1, _oe2 = build_memory(os.path.join(tmp, "onb_mem"))
    name_q = next(q for q in qs if q["key"] == "name")
    fact = ob.record(omem, name_q, "Yulian", scope=None)
    check("onboarding stores an answer as durable memory",
          "Yulian" in fact
          and any("Yulian" in p["content"] for p in omem.provenance("name", scope=None)))
    check("onboarding is not done until completed", not ob.is_done())
    ob.complete({"name": "Yulian"})
    check("onboarding marks done + remembers the name across restart",
          ob.is_done() and Onboarding(os.path.join(tmp, "onb.json")).name() == "Yulian")
    persona = ContextBuilder().build(Session(scope="demo"), ContextBundle(), None)[0]["content"]
    check("assistant identifies as Myro in its persona", persona.startswith("You are Myro"))
    check("assistant name is configurable",
          ContextBuilder(assistant_name="Zara")
          .build(Session(), ContextBundle(), None)[0]["content"].startswith("You are Zara"))

    # 31) timezone + working hours -> scheduling lines up with the user's day (Phase 19)
    print("\n31) timezone + working hours")
    from core import profile as prof
    # offset parsing is exact and deterministic (epoch 0 = 1970-01-01T00:00Z)
    check("UTC offset parses to the right wall-clock",
          prof.now_hhmm(prof.parse_timezone("UTC+2"), 0) == "02:00"
          and prof.now_hhmm(prof.parse_timezone("UTC-5"), 0) == "19:00")
    check("a city maps to a timezone", prof.parse_timezone("Berlin") is not None)
    check("short abbreviations don't false-match inside words",
          prof.parse_timezone("Atlanta") is None)   # 'la' must not match Atlanta
    check("working hours parse from free text",
          prof.parse_working_hours("9am to 6pm") == ("09:00", "18:00")
          and prof.parse_working_hours("9 to 5") == ("09:00", "17:00")
          and prof.parse_working_hours("9 to 6") == ("09:00", "18:00")   # end < start -> PM
          and prof.parse_working_hours("10:00-18:00") == ("10:00", "18:00"))
    check("derive builds a profile from onboarding answers",
          prof.derive({"location": "Berlin", "hours": "9 to 5"})
          == {"timezone": "Berlin", "work_start": "09:00", "work_end": "17:00"})

    # a daily routine fires at the user's local time, in their timezone
    tzp = prof.parse_timezone("UTC+2")
    tbase = 1_700_000_000.0
    r_tz = Routines(os.path.join(tmp, "tzsched.json"), Agent(_ScriptRouter([]), a_tools), tz=tzp)
    r_tz.add("brief", "morning brief")
    r_tz.schedule("brief", at=prof.now_hhmm(tzp, tbase))     # == the user's local HH:MM
    check("daily routine fires at the user's local time",
          any(f["name"] == "brief" for f in r_tz.run_due(now=tbase)))
    check("timezone flows into the routine scheduler", r_tz.tz is tzp)

    # 32) reach me — voice + phone notifications + telegram bridge (Phase 20)
    print("\n32) voice + notifications + telegram bridge")
    from core.voice import Speaker
    sp = Speaker(enabled=True)
    check("voice degrades cleanly with no TTS engine",
          isinstance(sp.speak("hello"), bool) and sp.speak("") is False)
    check("voice toggle works", sp.toggle(False) is False and sp.toggle(True) is True)

    from core import notify as notif
    check("notify reports no channel when unconfigured",
          "no notification channel" in notif.notify({}, "t", "m"))
    nt = notif.build_request({"ntfy_topic": "myro", "ntfy_server": "https://ntfy.sh"}, "Hi", "body")
    check("ntfy request targets the topic with a title",
          nt[0] == "https://ntfy.sh/myro" and nt[1] == b"body" and nt[2].get("Title") == "Hi")
    tg = notif.build_request({"telegram_token": "T", "telegram_chat_id": "42"}, "", "hey")
    check("telegram request posts to sendMessage for the chat",
          tg[0].endswith("/botT/sendMessage") and b"chat_id=42" in tg[1] and b"hey" in tg[1])
    check("channel selection prefers ntfy > telegram > pushover",
          notif.channel({"ntfy_topic": "x", "telegram_token": "T", "telegram_chat_id": "1"}) == "ntfy"
          and notif.channel({"telegram_token": "T", "telegram_chat_id": "1"}) == "telegram"
          and notif.channel({"pushover_token": "p", "pushover_user": "u"}) == "pushover"
          and notif.channel({}) is None)
    n_on = _bdt(None, allow_web=False, notify_config={"ntfy_topic": "x"}).get("notify")
    check("notify tool registers (unattended) only when a channel is set",
          n_on is not None and n_on.unattended
          and _bdt(None, allow_web=False, notify_config={}).get("notify") is None)

    from core.telegram_bridge import TelegramBridge

    class _FakeTgOrch:
        def __init__(self):
            self.turns = []

        def handle_turn(self, text, session, confirm=None):
            self.turns.append((text, confirm))
            return f"echo:{text}"

    class _FakeTgClient:
        def __init__(self, updates):
            self._u = list(updates)
            self.sent = []

        def get_updates(self, offset):
            return [u for u in self._u if u["update_id"] >= offset]

        def send_message(self, chat, text):
            self.sent.append((chat, text))

    ups = [
        {"update_id": 1, "message": {"chat": {"id": 42}, "text": "hi myro"}},
        {"update_id": 2, "message": {"chat": {"id": 999}, "text": "let me in"}},
        {"update_id": 3, "message": {"chat": {"id": 42}, "text": "  "}},
    ]
    fo, fc = _FakeTgOrch(), _FakeTgClient(ups)
    br = TelegramBridge(fo, fc, chat_id=42)
    handled = br.poll_once()
    check("telegram bridge relays only the authorized chat",
          handled == 1 and [t[0] for t in fo.turns] == ["hi myro"]
          and fc.sent == [("42", "echo:hi myro")])
    check("telegram turns run non-interactively (gated writes denied)",
          bool(fo.turns) and fo.turns[0][1] is None)
    check("telegram bridge advances offset + no re-processing",
          br._offset == 4 and br.poll_once() == 0)

    # 33) voice I/O — speak tool + speech-to-text + hands-free loop (Phase 22)
    print("\n33) voice input + speak tool")
    from core.listen import Listener
    from core.voice import Speaker as _Spk
    from core.voice_loop import VoiceLoop
    sp_tools = _bdt(None, allow_web=False, speaker=_Spk())
    check("speak tool registered + unattended (routine-usable)",
          sp_tools.get("speak") is not None and sp_tools.get("speak").unattended)
    check("speak tool returns a string, degrades with no engine",
          isinstance(sp_tools.get("speak").run({"text": "hello"}), str))
    check("speak(force) attempts even when voice is off (no crash)",
          _Spk(enabled=False).speak("hi", force=True) in (True, False))
    check("listener degrades cleanly when STT/mic is unavailable",
          isinstance(Listener().available(), bool) and Listener().listen() is None)

    class _FakeListener:
        def __init__(self, phrases):
            self._p = list(phrases)

        def available(self):
            return True

        def listen(self):
            return self._p.pop(0) if self._p else None

    class _FakeSpeaker:
        def __init__(self):
            self.said = []

        def speak(self, text, force=False):
            self.said.append((text, force))
            return True

    class _VLOrch:
        def __init__(self):
            self.turns = []

        def handle_turn(self, text, session, confirm=None):
            self.turns.append(text)
            return f"heard:{text}"

    fl = _FakeListener(["what's my name", "stop listening", ""])
    fsp, vlo = _FakeSpeaker(), _VLOrch()
    vl = VoiceLoop(vlo, fl, fsp)
    h1, r1 = vl.once()
    check("voice loop transcribes, answers, and speaks the reply",
          h1 == "what's my name" and r1 == "heard:what's my name"
          and vlo.turns == ["what's my name"] and fsp.said and fsp.said[0][1] is True)
    h2, r2 = vl.once()
    check("voice loop stops on a stop phrase",
          h2 == "__stop__" and vlo.turns == ["what's my name"])
    h3, r3 = vl.once()
    check("voice loop ignores empty input", h3 is None and r3 is None)

    # 34) wake word — always-listening, only acts after "Hey Myro" (Phase 23)
    print("\n34) wake word")
    from core.voice_loop import WakeLoop

    def _wake(phrases):
        return WakeLoop(_VLOrch(), _FakeListener(phrases), _FakeSpeaker(), wake="Myro")

    w1 = _wake(["hey myro what's my name"])
    c1, rp1 = w1.once()
    check("wake word + command in one breath runs the command",
          c1 == "what's my name" and rp1 == "heard:what's my name"
          and w1.orch.turns == ["what's my name"])
    w2 = _wake(["the weather is nice today"])
    c2, _ = w2.once()
    check("no wake word -> nothing happens", c2 is None and w2.orch.turns == [])
    w3 = _wake(["hey myro", "add milk to my list"])
    c3, _ = w3.once()
    check("wake word alone -> acknowledges, then takes the next command",
          c3 == "add milk to my list" and w3.orch.turns == ["add milk to my list"]
          and any("Yes" in t for t, _f in w3.speaker.said))
    w4 = _wake(["stop listening"])
    c4, _ = w4.once()
    check("wake loop stops on a stop phrase", c4 == "__stop__" and w4.orch.turns == [])
    w5 = _wake(["myron went to the store"])   # 'myro' inside a word must not trigger
    c5, _ = w5.once()
    check("wake matching respects word boundaries (no false trigger)",
          c5 is None and w5.orch.turns == [])

    # 35) browser app backend — the handlers behind the chat UI (Phase 24)
    print("\n35) web app backend")
    from core.onboarding import Onboarding as _OB
    from core.routines import Routines as _RT
    from interfaces.webapi import WebApp
    wtl = _bdt(None, allow_web=False, connectors={"git_repo": repo_root})
    wr = _ScriptRouter(['{"tool": "git_log", "args": {"n": 1}}', "Here's your latest commit."])
    worch = _orch(wr, wtl, Agent(wr, wtl), "web")
    worch.connectors = {"git_repo": repo_root}
    worch.routines = _RT(os.path.join(tmp, "web_rt.json"), Agent(_ScriptRouter([]), wtl))
    worch.onboarding = _OB(os.path.join(tmp, "web_onb.json"))
    worch.onboarding.complete({"name": "Yulian"})   # already onboarded: test the tool path
    wa = WebApp(worch)
    cres = wa.chat("show my latest commit", sid="s1", allow_actions=True)
    check("web chat returns a reply with tool steps",
          "commit" in cres["reply"].lower()
          and any(s["tool"] == "git_log" for s in cres["steps"]))
    st = wa.status("s1")
    check("web status reports name + memory count", st["name"] == "Myro" and "memory" in st)
    wa.remember("My cat is Milo.", scope=None)
    check("web remember + memory list", any("Milo" in x for x in wa.memory("cat")["items"]))
    wa.set_profile(name="Alex", timezone="Europe/Berlin", hours="9 to 6")
    prof = wa.profile()
    check("web profile derives timezone + hours",
          prof["name"] == "Alex" and "Berlin" in prof["timezone"]
          and prof["work_start"] == "09:00" and prof["work_end"] == "18:00")
    check("web connectors + tools listed",
          wa.connectors()["status"].get("git", "").startswith("ok")
          and any(t["name"] == "git_log" for t in wa.tools()["tools"]))
    wa.install_starters()
    wa.add_routine("hello", "say hi")
    names = [r["name"] for r in wa.routines()["routines"]]
    check("web routines install + add + list", "hello" in names and "phone_briefing" in names)
    sc = wa.schedule_routine("hello", "at 08:00")
    hello = next(r for r in wa.routines()["routines"] if r["name"] == "hello")
    check("web schedule a routine", sc["ok"] and "08:00" in hello["schedule"])

    gtl = _bdt(None, allow_web=False, connectors={"calendar_file": os.path.join(tmp, "web.ics")})
    gr = _ScriptRouter(['{"tool": "calendar_add_event", "args": {"title": "X", "start": "2030-01-01 09:00"}}', "ok"])
    gorch = _orch(gr, gtl, Agent(gr, gtl), "webg")
    gorch.routines = _RT(os.path.join(tmp, "wg.json"), Agent(_ScriptRouter([]), gtl))
    gorch.onboarding = _OB(os.path.join(tmp, "wg_onb.json"))
    gorch.onboarding.complete({})                    # skip the intro for this test
    dres = WebApp(gorch).chat("add an event", allow_actions=False)
    check("web read-only mode denies gated actions",
          any(s["tool"] == "calendar_add_event" and s["denied"] for s in dres["steps"]))

    # web onboarding parity: first message starts the interview, answers step
    # through, 'stop' finishes + marks it done, and it re-runs on a plain request.
    fob = _OB(os.path.join(tmp, "web_onb2.json"))
    ftl = _bdt(None, allow_web=False)
    forch = _orch(_ScriptRouter([]), ftl, Agent(_ScriptRouter([]), ftl), "webob")
    forch.routines = _RT(os.path.join(tmp, "web_rt2.json"), Agent(_ScriptRouter([]), ftl))
    forch.onboarding = fob
    wob = WebApp(forch)
    o_first = wob.chat("hey there", sid="o1")
    check("web onboarding auto-starts on the first message",
          bool(o_first.get("onboarding")) and "[1/" in o_first["reply"])
    o_name = wob.chat("Yulian", sid="o1")
    check("web onboarding advances to the next question after an answer",
          "[2/" in o_name["reply"])
    o_stop = wob.chat("stop", sid="o1")
    check("web onboarding finishes on 'stop', marks done + remembers the name",
          fob.is_done() and fob.name() == "Yulian" and "great start" in o_stop["reply"])
    o_after = wob.chat("what can you do", sid="o2")
    check("web onboarding does not re-trigger once done", not o_after.get("onboarding"))
    o_rerun = wob.chat("can you ask me the introduction question to get to know me better",
                       sid="o3")
    check("web onboarding re-runs on a natural-language request",
          bool(o_rerun.get("onboarding")) and "[1/" in o_rerun["reply"])

    idx = os.path.join(repo_root, "interfaces", "static", "index.html")
    with open(idx, encoding="utf-8") as f:
        html = f.read()
    check("web app page exists and wires the chat API",
          "/api/" in html and "chat" in html and "Myro" in html and "speechSynthesis" in html)

    # one-shot install: the `all` extra bundles every superpower so a single
    # `pip install -e ".[all]"` (or Setup.bat) sets Myro up fully.
    import tomllib
    with open(os.path.join(repo_root, "pyproject.toml"), "rb") as f:
        _pp = tomllib.load(f)
    _all = " ".join(_pp["project"]["optional-dependencies"].get("all", []))
    check("pyproject '[all]' extra bundles the superpowers in one install",
          all(k in _all for k in ("serve", "browser", "voice", "backup",
                                  "schedule", "subscription")))

    # brain preference: keep everyday chat on the local model, or auto-route.
    from core import brain as _brn
    from core.policy import Policy as _Pol
    from core.router import Router as _Rtr

    class _BM:
        def __init__(self, local): self.is_local = local

    class _BReg:
        def __init__(self, models, defaults): self._m = models; self._d = defaults
        def default_name(self, intent): return self._d.get(intent)
        def get(self, n): return self._m.get(n)
        def names(self): return list(self._m)
        def fallback(self): return self._m.get("echo")

    _reg = _BReg({"loc": _BM(True), "cloud": _BM(False), "echo": _BM(True)},
                 {"private": "loc", "general": "cloud", "hard_reasoning": "cloud", "fallback": "echo"})
    _pol = _Pol()
    check("brain prefer-local pins general+hard_reasoning to a local model",
          _brn.apply_preference(_pol, _reg, True)
          and _pol.routing_rules.get("general") == "loc"
          and _pol.routing_rules.get("hard_reasoning") == "loc")
    check("brain is_local_preferred reflects the pinned rule",
          _brn.is_local_preferred(_pol, _reg))
    _brn.apply_preference(_pol, _reg, False)
    check("brain auto clears the local pin",
          "general" not in _pol.routing_rules and not _brn.is_local_preferred(_pol, _reg))
    _pol2 = _Pol()
    _reg2 = _BReg({"cloud": _BM(False)}, {"general": "cloud", "hard_reasoning": "cloud"})
    check("brain prefer-local no-ops gracefully when no local model exists",
          _brn.apply_preference(_pol2, _reg2, True) is False and "general" not in _pol2.routing_rules)
    _bd = os.path.join(tmp, "brainpref"); os.makedirs(_bd, exist_ok=True)
    _brn.save_pref(_bd, True)
    check("brain preference persists + reloads",
          _brn.load_pref(_bd) is True and _brn.load_pref(os.path.join(tmp, "nope")) is None)

    os.environ["AGI_PREFER_LOCAL"] = "1"
    try:
        from config.settings import Settings as _Set
        check("AGI_PREFER_LOCAL env is honored by Settings", _Set.load().prefer_local is True)
    finally:
        os.environ.pop("AGI_PREFER_LOCAL", None)

    # web app path: the Settings toggle switches brains and reports the active one.
    class _BrainOrch:
        def __init__(self, reg):
            self.policy = _Pol(); self.router = _Rtr(reg, self.policy)
            self.data_dir = os.path.join(tmp, "brainweb")
            self.context_builder = ContextBuilder(); self.onboarding = None
    _bwa = WebApp(_BrainOrch(_BReg(
        {"loc": _BM(True), "cloud": _BM(False), "echo": _BM(True)},
        {"private": "loc", "general": "cloud", "hard_reasoning": "cloud", "fallback": "echo"})))
    _rl = _bwa.set_brain("local")
    check("web set_brain local switches to a local brain",
          _rl["ok"] and _rl["mode"] == "local" and _rl["local"])
    _ra = _bwa.set_brain("auto")
    check("web set_brain auto returns to cloud routing",
          _ra["mode"] == "auto" and not _ra["local"])

    # 36) backups — snapshot everything you built (Phase 25)
    print("\n36) backups")
    import tarfile as _tf

    from core import backup as bk
    bdata = os.path.join(tmp, "bk_data")
    os.makedirs(os.path.join(bdata, "vectors"))
    with open(os.path.join(bdata, "episodic.db"), "w") as f:
        f.write("episodes")
    with open(os.path.join(bdata, "vectors", "semantic.db"), "w") as f:
        f.write("vectors")
    bdest = os.path.join(tmp, "bk_out")
    snap = bk.snapshot(bdata, bdest)
    with _tf.open(snap) as t:
        arc = t.getnames()
    check("backup snapshots the data into an archive",
          snap.endswith(".tar.gz") and any("episodic.db" in n for n in arc)
          and any("semantic.db" in n for n in arc))
    rdir = os.path.join(tmp, "bk_restore")
    check("backup restores round-trip",
          bk.restore(snap, rdir) and os.path.exists(os.path.join(rdir, "episodic.db")))
    for i in range(3):
        bk.snapshot(bdata, bdest, now=1000 + i * 3600)
    check("rotate keeps only N snapshots",
          bk.rotate(bdest, keep=2) >= 1
          and len([f for f in os.listdir(bdest) if f.startswith("myro-backup-")]) == 2)
    res = bk.run_backup({"data_dir": bdata, "backup_dir": os.path.join(tmp, "bk_run"),
                         "backup_keep": 5})
    check("run_backup makes a local snapshot (no push by default)",
          res["ok"] and res["snapshot"].startswith("myro-backup-") and res["pushed"] is None)
    check("git backup command is a proper git push",
          bk._git_backup_cmds("/repo", "s.tar.gz")[-1] == ["git", "-C", "/repo", "push"])
    check("encrypt round-trips when crypto is available (else skipped)",
          _enc_roundtrip(bk, snap, os.path.join(tmp, "bk_enc")))
    btools = _bdt(None, allow_web=False, backup_config={"data_dir": bdata})
    check("backup tool registered + unattended (schedulable)",
          btools.get("backup") is not None and btools.get("backup").unattended)
    from core.starter_routines import STARTERS as _ST
    check("nightly backup starter is available",
          any(s["name"] == "backup" for s in _ST))

    print()
    if all(_results):
        print(f"All {len(_results)} checks {PASS}")
        return 0
    print(f"{sum(1 for r in _results if not r)}/{len(_results)} checks {FAIL}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
