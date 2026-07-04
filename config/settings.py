"""Configuration — filesystem paths, tuning knobs, and the model registry config.

Paths and knobs come from dataclass defaults. The model registry is loaded from
config/models.yaml so adding/swapping a backend is a config change, not a code
change. Loading is defensive: if the file or PyYAML is missing, a built-in
default (the offline echo backend) keeps the layer bootable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MODELS_YAML = ROOT / "config" / "models.yaml"


# Minimal built-in fallback so the layer boots even without models.yaml/PyYAML.
_DEFAULT_MODELS_CONFIG = {
    "models": [
        {"name": "echo", "adapter": "echo", "context_window": 8000,
         "capabilities": [], "privacy": "local", "cost": "free"},
    ],
    "defaults": {
        "hard_reasoning": "echo", "general": "echo",
        "private": "echo", "fallback": "echo",
    },
}


def _load_models_config(path: Path) -> dict:
    """Parse models.yaml, falling back to the built-in default if the file or
    PyYAML is unavailable — the system always has at least the echo backend and
    never fails to boot on config alone."""
    try:
        import yaml  # optional dependency
    except Exception:
        return dict(_DEFAULT_MODELS_CONFIG)
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return dict(_DEFAULT_MODELS_CONFIG)
    cfg.setdefault("models", [])
    cfg.setdefault("defaults", {})
    return cfg


@dataclass
class Settings:
    data_dir: Path = DATA_DIR
    episodic_db: Path = DATA_DIR / "episodic.db"
    vector_dir: Path = DATA_DIR / "vectors"
    graph_dir: Path = DATA_DIR / "graph"

    # Retrieval knobs — the main things to tune when it feels off.
    retrieval_budget_tokens: int = 6000
    rrf_k: int = 60
    recency_half_life_days: float = 30.0

    # Consolidation schedule (cron). Default: 3am daily.
    consolidation_cron: str = "0 3 * * *"

    # Scopes whose turns must never leave the machine (router forces a local
    # model). Scopes containing private/sensitive/health/finance/etc. are also
    # treated as sensitive by convention.
    sensitive_scopes: tuple = ()

    # Semantic memory backend: "native" (owned SQLite vector store — unlocks
    # reconcile-on-write, decay, and temporal supersede) or "mem0" (hybrid).
    semantic_backend: str = "native"

    # Local embedding model for the native semantic store (a sentence-transformers
    # name, or an Ollama tag). Falls back to a hashing embedding if unavailable.
    embedding_model: str = "all-MiniLM-L6-v2"

    # Optional: the user's name, so the assistant can greet them personally.
    user_name: str | None = None

    # Web/browser tools for the agent (web_search + hardened web_fetch). Set
    # False for an air-gapped layer with no outbound HTTP from tools.
    allow_web: bool = True

    # Connectors (git / calendar / email) — read your real world, locally. Set
    # allow_connectors False to omit them entirely; otherwise the paths below are
    # the defaults the connector tools use (each also accepts a path argument).
    allow_connectors: bool = True
    git_repo: str | None = None        # default repo for git_log/git_status (None -> ".")
    calendar_file: str | None = None   # path to an .ics for calendar_upcoming
    mailbox_file: str | None = None    # path to an mbox for email_recent

    # How often (seconds) the background tick checks for due scheduled routines.
    routine_tick_seconds: float = 60.0

    # Model registry, parsed from config/models.yaml (see _load_models_config).
    models_config: dict = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Settings":
        s = cls(models_config=_load_models_config(MODELS_YAML))
        for p in (s.data_dir, s.vector_dir, s.graph_dir):
            p.mkdir(parents=True, exist_ok=True)
        return s
