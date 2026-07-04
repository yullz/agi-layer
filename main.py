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

from config.settings import Settings
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
from memory.semantic import SemanticStore
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
    embedder = Embedder("your-embedding-model")
    reranker = Reranker("your-cross-encoder")
    registry = ModelRegistry(cfg.models_config, FrontierModel, LocalModel)

    # --- Stores ---
    episodic = EpisodicStore(cfg.episodic_db)
    semantic = SemanticStore(cfg.vector_dir, embedder)
    graph = GraphStore(cfg.graph_dir)
    procedural = ProceduralStore(cfg.episodic_db)

    # --- Memory pipelines ---
    write_pipeline = WritePipeline(episodic=episodic, semantic=semantic, graph=graph)
    consolidator = Consolidator(
        episodic=episodic, semantic=semantic, graph=graph,
        half_life_days=cfg.recency_half_life_days,
    )

    memory = MemoryStore(
        episodic=episodic, semantic=semantic, graph=graph, procedural=procedural,
        embedder=embedder, reranker=None,  # Phase 1: no cross-encoder wired yet
        write_pipeline=write_pipeline, consolidator=consolidator,
        half_life_days=cfg.recency_half_life_days,
        budget_tokens=cfg.retrieval_budget_tokens,
    )

    # --- Core ---
    policy = Policy()
    orchestrator = Orchestrator(
        memory=memory,
        router=Router(registry, policy),
        context_builder=ContextBuilder(),
        skills=Skills(),
        feedback=Feedback(),
        retrieval_budget_tokens=cfg.retrieval_budget_tokens,
    )
    return cfg, orchestrator


def main():
    _cfg, orchestrator = build()
    # TODO: start a background scheduler that calls memory.consolidate() on
    #       cfg.consolidation_cron (APScheduler), and optionally serve
    #       interfaces/api.py or interfaces/mcp.py instead of the CLI.
    run_repl(orchestrator, Session())


if __name__ == "__main__":
    main()
