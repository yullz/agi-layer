"""Boot — wire dependencies and start the layer.

This is the composition root: every concrete implementation is chosen here and
injected inward, so the modules stay decoupled and swappable. As you implement
the stubs, only this file needs to know which concrete stores/models you picked;
the wiring shape stays the same.

As of Phase 1 (hybrid memory) this boots: it wires the real SQLite episodic
store, a Mem0-backed semantic store (which degrades gracefully if Mem0 isn't
configured), and an offline echo model, so the turn loop runs with no API key.
Set a frontier key or start a local Ollama model to enable real generation.
"""
from __future__ import annotations

import os

from config.settings import Settings
from governance.audit import Audit
from governance.guardrails import Guardrails
from governance.versioning import Versioning
from improvement.optimizer import Optimizer
from core.agent import Agent
from core.browser_agent import BrowserPilot
from core.context_builder import ContextBuilder
from core.onboarding import Onboarding
from core.orchestrator import Orchestrator
from core.policy import Policy
from core.profile import parse_timezone
from core.router import Router
from core.routines import Routines
from core.session import Session
from core.tools import build_default_tools
from improvement.feedback import Feedback
from improvement.skills import Skills
from interfaces.cli import run_repl
from memory.consolidation import Consolidator
from memory.episodic import EpisodicStore
from memory.graph import GraphStore
from memory.procedural import ProceduralStore
from memory.extractor import LLMExtractor
from memory.semantic import SemanticStore
from memory.semantic_native import NativeSemanticStore
from memory.store import MemoryStore
from memory.write_path import WritePipeline
from models.embeddings import Embedder
from models.local import LocalModel
from models.frontier import FrontierModel
from models.registry import ModelRegistry
from models.reranker import Reranker


def build():
    cfg = Settings.load()

    # --- Models ---
    embedder = Embedder(cfg.embedding_model)
    reranker = Reranker()  # lazy cross-encoder; identity passthrough if absent
    registry = ModelRegistry(cfg.models_config, FrontierModel, LocalModel)
    # LLM extraction / contradiction / relation detection runs on the private
    # (local) model for privacy; degrades to heuristics when unreachable.
    extractor = LLMExtractor(registry.local_private())

    # --- Stores ---
    episodic = EpisodicStore(cfg.episodic_db)
    if cfg.semantic_backend == "mem0":
        semantic = SemanticStore(cfg.vector_dir, embedder)      # hybrid engine
    else:
        semantic = NativeSemanticStore(cfg.vector_dir, embedder, extractor=extractor)
    graph = GraphStore(cfg.graph_dir)
    procedural = ProceduralStore(cfg.episodic_db)

    # --- Memory pipelines ---
    write_pipeline = WritePipeline(episodic=episodic, semantic=semantic, graph=graph,
                                   extractor=extractor)
    consolidator = Consolidator(
        episodic=episodic, semantic=semantic, graph=graph,
        summarizer=registry.local_private(),
        half_life_days=cfg.recency_half_life_days,
    )

    memory = MemoryStore(
        episodic=episodic, semantic=semantic, graph=graph, procedural=procedural,
        embedder=embedder, reranker=reranker,
        write_pipeline=write_pipeline, consolidator=consolidator,
        half_life_days=cfg.recency_half_life_days,
        budget_tokens=cfg.retrieval_budget_tokens,
    )

    # --- Core + governance ---
    policy = Policy()
    guardrails = Guardrails()
    versioning = Versioning(cfg.data_dir / "versions")
    audit = Audit(cfg.data_dir / "audit.jsonl")
    router = Router(registry, policy, sensitive_scopes=cfg.sensitive_scopes)
    orchestrator = Orchestrator(
        memory=memory,
        router=router,
        context_builder=ContextBuilder(user_name=cfg.user_name,
                                       assistant_name=cfg.assistant_name),
        skills=Skills(model=registry.local_private(),
                      registry_dir=cfg.data_dir / "skills",
                      guardrails=guardrails, audit=audit),
        feedback=Feedback(path=cfg.data_dir / "feedback.jsonl"),
        retrieval_budget_tokens=cfg.retrieval_budget_tokens,
        optimizer=Optimizer(),
        policy=policy,
        guardrails=guardrails,
        versioning=versioning,
        audit=audit,
    )

    # --- Agent execution layer (the "hands") ---
    # Tools + a governed, model-agnostic tool-use loop, plus saved routines.
    # Every tool call is audited; write/exec tools are gated (confirm required),
    # and routines run unattended so those gated tools are denied fail-closed.
    connectors = ({"git_repo": cfg.git_repo, "calendar_file": cfg.calendar_file,
                   "mailbox_file": cfg.mailbox_file, "github_repo": cfg.github_repo,
                   "github_token": cfg.github_token, "imap_host": cfg.imap_host,
                   "imap_user": cfg.imap_user, "imap_password": cfg.imap_password,
                   "smtp_host": cfg.smtp_host, "smtp_user": cfg.smtp_user,
                   "smtp_password": cfg.smtp_password, "smtp_from": cfg.smtp_from,
                   "smtp_port": cfg.smtp_port}
                  if cfg.allow_connectors else None)
    pilot = BrowserPilot(router) if cfg.allow_web else None
    notify_config = {"ntfy_topic": cfg.ntfy_topic, "ntfy_server": cfg.ntfy_server,
                     "telegram_token": cfg.telegram_token,
                     "telegram_chat_id": cfg.telegram_chat_id,
                     "pushover_token": cfg.pushover_token, "pushover_user": cfg.pushover_user}
    tools = build_default_tools(memory, allow_web=cfg.allow_web, connectors=connectors,
                                browser_pilot=pilot, notify_config=notify_config)
    orchestrator.tools = tools
    orchestrator.connectors = connectors
    orchestrator.notify_config = notify_config
    orchestrator.voice_enabled = cfg.voice_enabled
    orchestrator.agent = Agent(router, tools, audit=audit)
    # Timezone from config, else derived from the onboarding location answer, so
    # daily routines fire at the user's local wall-clock.
    onboarding = Onboarding(cfg.data_dir / "onboarding.json")
    tz = parse_timezone(cfg.timezone or onboarding.timezone())
    orchestrator.routines = Routines(cfg.data_dir / "routines.json",
                                     orchestrator.agent, tz=tz)
    orchestrator.onboarding = onboarding
    return cfg, orchestrator


def main():
    cfg, orchestrator = build()
    # Background consolidation ("sleep") on the configured cron — APScheduler if
    # installed, else a stdlib timer fallback.
    from core.scheduler import Scheduler
    scheduler = Scheduler(orchestrator.memory.consolidate, cron=cfg.consolidation_cron)
    scheduler.start()
    # Minute-tick that fires any scheduled routines that are due (time-based
    # automation). run_due() is a cheap no-op when nothing is scheduled.
    routine_tick = Scheduler(orchestrator.routines.run_due, cron="* * * * *",
                             interval_seconds=cfg.routine_tick_seconds)
    routine_tick.start()
    try:
        # Choose an interface: cli (default) | api | mcp | telegram.
        iface = os.environ.get("AGI_INTERFACE", "cli").lower()
        if iface == "api":
            from interfaces.api import build_app, serve
            serve(build_app(orchestrator))
        elif iface == "mcp":
            from interfaces.mcp import build_mcp_server
            build_mcp_server(orchestrator.memory, orchestrator).run()
        elif iface == "telegram":
            from interfaces.telegram import serve_telegram
            serve_telegram(orchestrator, cfg)
        else:
            run_repl(orchestrator, Session())
    finally:
        routine_tick.stop()
        scheduler.stop()
        orchestrator.memory.close()


if __name__ == "__main__":
    main()
