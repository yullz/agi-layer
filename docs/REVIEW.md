# Code review — fixed & deferred

A multi-agent audit (7 dimensions, adversarially verified, 90 findings) ran over
the whole codebase. This tracks what was fixed and what's intentionally deferred,
honestly.

## Fixed (Phase 9)

**Privacy boundary**
- Retrieval is destination-aware: `MemoryStore.retrieve(for_external=)` drops
  sensitive-scope candidates before they can reach a cloud model; the turn loop
  routes first and sets `for_external = not model.is_local`.
- Extractor, consolidation summarizer, and skills model all go through
  `registry.local_private()` — an on-box model, never a cloud one.
- Shared `memory/scope.is_sensitive_scope` with broadened hints.

**Smartness**
- Scope is hierarchical: retrieval returns the active scope **plus global**
  (`scope IS ? OR scope IS NULL`) across semantic / episodic / graph — so
  seeded/identity facts surface inside project scopes, and a global session no
  longer sees every project's rows.
- `score_final` relevance is rank-normalised to [0,1] and reweighted so relevance
  dominates (was ~0.02 vs ~0.7 importance+recency); reranker logits sigmoid-squashed.
- `_cosine` returns 0 on dimension mismatch (no more mixed-embedding garbage);
  `main` uses a real embedder instead of the `"your-embedding-model"` placeholder.
- Graph reads match known entity names case-insensitively (`entities_in_text`);
  graph candidates carry real recency/importance.
- Seeding is idempotent (deterministic ids); the heuristic no longer stores
  questions as facts.

**Robustness / UX**
- `router.generate()` falls back to an on-box model if generation raises (turn
  degrades, never aborts); `_cosine`, `close()` on stores, `MemoryStore.close()`.
- Project logger (`core/log`); ingest failures logged, not silently swallowed.
- Warm system-prompt persona, welcome banner + memory count, `:help` / `:status`
  / `:about` / `:memory`, model attribution, friendly copy, whole-REPL guard.
- README rewritten (was falsely "a scaffold that crashes"); `pyproject.toml`
  (+ `agi-layer` console script, extras), `.env.example`, SETUP, CI, `.gitignore`.

## Deferred (worth doing, tracked)

**Security**
- **Skill sandbox is not a real boundary.** The restricted-`exec` is escapable
  (`().__class__.__base__.__subclasses__()`), and persisted skills are exec'd on
  load. It's fail-closed by default (`skill_author` not allowed, `data/skills`
  empty), but before enabling authoring: run candidates in a subprocess with
  rlimits, replace the substring screen with an AST walk, and re-screen on load
  with a hash allow-list.
- MCP/HTTP surfaces are unauthenticated — add a local token + per-client scope
  allow-list and deny sensitive scopes over the wire before non-localhost use.

**Performance / correctness**
- `write_async` still runs ingest inline (no real background worker yet) — a slow
  Ollama extraction blocks the turn. Add a queue + daemon consumer, or cap
  synchronous ingest with a timeout.
- Embedding-model/dim columns + a `re_embed` consolidation pass so switching
  embedders self-heals the whole hot set (today mismatched rows just score 0).
- Offline reconcile can't detect contradictions (hash embedding) — add a
  same-subject/predicate heuristic so stale facts get superseded without an LLM.
- `_hash_embed` is unweighted bag-of-tokens (no stopwords) — over-merges short
  facts; add stopword/idf weighting + a Jaccard guard.
- Importance saturates (+0.05 per touch pegs at 1.0); consolidation `_promote`
  re-mines already-ingested episodes. Use a `base_importance` prior + diminishing
  returns; make promote idempotent via a per-episode flag.
- Content-dedup after fusion (a fact stored as both a MemoryItem and its Episode
  is packed twice); exclude the active session from the recency retriever.
- Per-scope consolidation watermark (a scope trickling <3 episodes/run is never
  summarized); embedding cache to avoid full-scan + JSON re-parse per retrieval.
- Scheduler timer path ignores the cron and runs the first tick 24h out; audit
  log has no tamper-evidence; FTS can accumulate duplicate rows.

**Hygiene**
- pytest unit suite per subsystem (smoke.py is the end-to-end gate);
  a `SemanticStore` Protocol so native/mem0 stop diverging; implement or remove
  the dead `ProceduralStore`; one `estimate_tokens()` helper.
