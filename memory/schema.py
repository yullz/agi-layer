"""Core data model shared across the layer.

These dataclasses define the whole memory contract. Every other module —
stores, retrieval, consolidation, the core — operates on these types, so keep
this file the single source of truth for shapes.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


def _id() -> str:
    return uuid.uuid4().hex


def _now() -> float:
    return time.time()


# A project/domain tag, e.g. "longevity-code", "whaletrack", "ocado".
# Scope is a first-class filter on both write and read so parallel projects
# don't bleed into each other's context.
Scope = str


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class ItemKind(str, Enum):
    FACT = "fact"              # durable statement about the user or their world
    SUMMARY = "summary"        # compressed rollup produced by consolidation
    PREFERENCE = "preference"  # a stated or demonstrated preference


class Source(str, Enum):
    VECTOR = "vector"
    KEYWORD = "keyword"
    GRAPH = "graph"
    RECENCY = "recency"


@dataclass
class Episode:
    """One raw logged event in the episodic store."""
    id: str = field(default_factory=_id)
    ts: float = field(default_factory=_now)
    session_id: str = ""
    role: Role = Role.USER
    content: str = ""
    scope: Scope | None = None
    model: str | None = None
    tool_calls: list[dict] = field(default_factory=list)
    latency_ms: int | None = None
    feedback: float | None = None   # -1..1, set later when signal arrives


@dataclass
class MemoryItem:
    """An atomic, retrievable unit of semantic memory."""
    id: str = field(default_factory=_id)
    content: str = ""
    kind: ItemKind = ItemKind.FACT
    scope: Scope | None = None

    # Forgetting-curve fields: importance is boosted on retrieval and decayed
    # when the item goes cold (see consolidation + retrieval.score_final).
    importance: float = 0.5           # 0..1
    created_at: float = field(default_factory=_now)
    last_accessed: float = field(default_factory=_now)
    access_count: int = 0

    # Temporal fields: facts change. Never overwrite — supersede, so history
    # is preserved and "what did I used to..." stays answerable.
    valid_from: float = field(default_factory=_now)
    superseded_by: str | None = None  # id of the item that replaced this one

    source_episode_ids: list[str] = field(default_factory=list)
    embedding_model: str | None = None
    embedding: list[float] | None = None

    @property
    def is_current(self) -> bool:
        return self.superseded_by is None


@dataclass
class Entity:
    id: str = field(default_factory=_id)
    name: str = ""
    type: str = ""                    # person | project | tool | preference | ...
    scope: Scope | None = None
    attributes: dict = field(default_factory=dict)


@dataclass
class Relation:
    id: str = field(default_factory=_id)
    src: str = ""                     # entity id
    dst: str = ""                     # entity id
    type: str = ""                    # works_on | uses | prefers | ...
    scope: Scope | None = None
    valid_from: float = field(default_factory=_now)
    superseded_by: str | None = None


@dataclass
class Turn:
    """A completed exchange, handed to MemoryStore.write()."""
    session_id: str = ""
    scope: Scope | None = None
    user_input: str = ""
    assistant_reply: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    model: str | None = None
    ts: float = field(default_factory=_now)

    @classmethod
    def from_session(cls, session) -> "Turn":
        return session.to_turn()


@dataclass
class RetrievalCandidate:
    """A single hit flowing through the retrieval pipeline. Every retriever
    (vector, keyword, graph, recency) emits these so they can be fused."""
    ref_id: str = ""                  # MemoryItem.id or Episode.id
    content: str = ""
    source: Source = Source.VECTOR
    scope: Scope | None = None
    rank: int = 0                     # rank within its own retriever's list
    raw_score: float = 0.0            # native score (NOT comparable across sources)
    importance: float = 0.5
    created_at: float = field(default_factory=_now)
    token_estimate: int = 0
    fused_score: float = 0.0          # set by reciprocal rank fusion
    final_score: float = 0.0          # fused x importance x recency, after rerank


@dataclass
class ContextBundle:
    """The packed result the core injects into the prompt."""
    items: list[RetrievalCandidate] = field(default_factory=list)
    token_count: int = 0
    summary_of_dropped: str = ""
    provenance: list[str] = field(default_factory=list)  # ref_ids, for the audit trail
