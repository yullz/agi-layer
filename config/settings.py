"""Configuration — filesystem paths, tuning knobs, and the model registry config.

Paths and knobs come from dataclass defaults. The model registry is loaded from
config/models.yaml so adding/swapping a backend is a config change, not a code
change. Loading is defensive: if the file or PyYAML is missing, a built-in
default (the offline echo backend) keeps the layer bootable.
"""
from __future__ import annotations

import os
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

    # The assistant's name (its identity in the persona + interface).
    assistant_name: str = "Myro"

    # Optional timezone override (IANA name, a city, or a UTC offset like
    # "UTC+2"). If unset, it's derived from the onboarding location answer so
    # daily routines fire at your local wall-clock; else the machine's local time.
    timezone: str | None = None

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
    calendar_file: str | None = None   # an .ics path OR a published .ics URL
    mailbox_file: str | None = None    # path to an mbox for email_recent
    # Networked connectors (read-only). GitHub works on public repos with no
    # token; a token unlocks private repos. IMAP creds stay on your machine.
    github_repo: str | None = None     # owner/name for github_* tools
    github_token: str | None = None    # unlocks private repos + issue creation
    imap_host: str | None = None
    imap_user: str | None = None
    imap_password: str | None = None
    # SMTP send (gated tool). Credentials stay on your machine. Port 587 uses
    # STARTTLS; 465 uses TLS-on-connect (SMTP_SSL) automatically.
    smtp_host: str | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_port: int = 587

    # How often (seconds) the background tick checks for due scheduled routines.
    routine_tick_seconds: float = 60.0

    # Backups — snapshot data/ locally (point backup_dir at a synced drive for
    # off-site backup). Optional: a passphrase to encrypt, and a local clone of a
    # PRIVATE git repo to also push snapshots to GitHub.
    backup_dir: str | None = None            # default: <data>/backups
    backup_keep: int = 7
    backup_passphrase: str | None = None     # AGI_BACKUP_PASSPHRASE (needs `cryptography`)
    backup_git_dir: str | None = None        # AGI_BACKUP_GIT_DIR

    # Voice — speak replies aloud via a local TTS engine (CLI). Off by default.
    voice_enabled: bool = False
    # Wake word for the hands-free voice interface (AGI_INTERFACE=voice). Myro
    # only acts after he hears this. Set empty to listen continuously (no wake).
    wake_word: str = "Myro"

    # Reach your phone: a Telegram bridge (text Myro anywhere) + push
    # notifications (ntfy self-hostable / Telegram / Pushover). Credentials via
    # env vars so they never live in code (see load()).
    telegram_token: str | None = None
    telegram_chat_id: str | None = None
    ntfy_topic: str | None = None
    ntfy_server: str = "https://ntfy.sh"
    pushover_token: str | None = None
    pushover_user: str | None = None

    # Model registry, parsed from config/models.yaml (see _load_models_config).
    models_config: dict = field(default_factory=dict)
    # Brain preference: keep everyday chat on the on-box (local) model even when a
    # cloud brain is configured — private + free. Seeds the first run; the web app
    # toggle (persisted in data/brain.json) governs after that. AGI_PREFER_LOCAL.
    prefer_local: bool = False

    @classmethod
    def load(cls) -> "Settings":
        s = cls(models_config=_load_models_config(MODELS_YAML))
        # Environment overrides for user-configurable / secret fields, so tokens
        # and personal settings never have to live in the code.
        def _ov(attr, key, cast=str):
            v = os.environ.get(key)
            if v not in (None, ""):
                setattr(s, attr, cast(v))
        _ov("assistant_name", "AGI_ASSISTANT_NAME")
        _ov("user_name", "AGI_USER_NAME")
        _ov("timezone", "AGI_TIMEZONE")
        _ov("voice_enabled", "AGI_VOICE", lambda v: v.strip().lower() in ("1", "on", "true", "yes"))
        _ov("prefer_local", "AGI_PREFER_LOCAL", lambda v: v.strip().lower() in ("1", "on", "true", "yes"))
        _ov("wake_word", "AGI_WAKE_WORD")
        _ov("backup_dir", "AGI_BACKUP_DIR")
        _ov("backup_git_dir", "AGI_BACKUP_GIT_DIR")
        _ov("backup_passphrase", "AGI_BACKUP_PASSPHRASE")
        _ov("telegram_token", "AGI_TELEGRAM_TOKEN")
        _ov("telegram_chat_id", "AGI_TELEGRAM_CHAT_ID")
        _ov("ntfy_topic", "AGI_NTFY_TOPIC")
        _ov("ntfy_server", "AGI_NTFY_SERVER")
        _ov("pushover_token", "AGI_PUSHOVER_TOKEN")
        _ov("pushover_user", "AGI_PUSHOVER_USER")
        _ov("github_token", "AGI_GITHUB_TOKEN")
        _ov("github_repo", "AGI_GITHUB_REPO")
        # Relocate all of Myro's data (e.g. onto a synced drive), and avoid
        # writing into a read-only install tree. The derived paths are frozen
        # from DATA_DIR at class-definition time, so recompute them from the base.
        base = os.environ.get("AGI_DATA_DIR")
        if base:
            root = Path(base).expanduser()
            s.data_dir = root
            s.episodic_db = root / "episodic.db"
            s.vector_dir = root / "vectors"
            s.graph_dir = root / "graph"
        for p in (s.data_dir, s.vector_dir, s.graph_dir):
            p.mkdir(parents=True, exist_ok=True)
        return s
