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
from core.context_builder import ContextBuilder
from core.orchestrator import Orchestrator
from core.policy import Policy
from core.router import Router
from core.session import Session
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
    orchestrator = Orchestrator(
        memory=memory,
        router=Router(registry, policy, sensitive_scopes=cfg.sensitive_scopes),
        context_builder=ContextBuilder(user_name=cfg.user_name),
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
    return cfg, orchestrator


def main():
    cfg, orchestrator = build()
    # Background consolidation ("sleep") on the configured cron — APScheduler if
    # installed, else a stdlib timer fallback.
    from core.scheduler import Scheduler
    scheduler = Scheduler(orchestrator.memory.consolidate, cron=cfg.consolidation_cron)
    scheduler.start()
    try:
        # Choose an interface: cli (default) | api | mcp.
        iface = os.environ.get("AGI_INTERFACE", "cli").lower()
        if iface == "api":
            from interfaces.api import build_app, serve
            serve(build_app(orchestrator))
        elif iface == "mcp":
            from interfaces.mcp import build_mcp_server
            build_mcp_server(orchestrator.memory, orchestrator).run()
        else:
            run_repl(orchestrator, Session())
    finally:
        scheduler.stop()
        orchestrator.memory.close()


if __name__ == "__main__":
    main()
