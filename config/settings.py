"""Configuration — loaded from env + config/models.yaml."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


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

    @classmethod
    def load(cls) -> "Settings":
        s = cls()
        for p in (s.data_dir, s.vector_dir, s.graph_dir):
            p.mkdir(parents=True, exist_ok=True)
        return s
