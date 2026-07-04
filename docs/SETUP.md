# Setup — turning on real intelligence

agi-layer runs offline out of the box (echo model + hashing embeddings). Each
step below switches on a real capability. Do them in any order.

## 0. Install & run

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\Activate.ps1
pip install -e .           # core only; add extras below
python main.py             # REPL; :seed then :memory; :help for commands
python tests/smoke.py      # 42 offline checks
```

## 1. Claude on your Pro/Max subscription (default, no API credits)

```bash
pip install -e ".[subscription]"     # claude-agent-sdk
claude login                          # OAuth — draws from your plan, not credits
```
The router now prefers Claude for hard/general (non-sensitive) queries. Verify:
`:status` shows a claude model, and replies tag `[via claude-...]`. Rate-limited
by your plan; heavy automated volume can hit caps.

*Prefer pay-per-token API instead?* `pip install -e ".[frontier]"`, set
`ANTHROPIC_API_KEY`, and uncomment the `claude-api` entry in `config/models.yaml`.

## 2. Local model (private scopes + always-on fallback)

```bash
# install Ollama (https://ollama.com), then:
ollama pull qwen3:14b            # generation + fact extraction (fits a 16GB GPU)
ollama pull nomic-embed-text     # optional: embeddings via Ollama
```
`qwen-local` becomes reachable automatically. Sensitive scopes (see below) route
here, never to Claude.

## 3. Real embeddings (much better recall than the offline fallback)

```bash
pip install -e ".[rerank]"       # sentence-transformers: all-MiniLM + cross-encoder
```
The native store uses real embeddings + a reranker when present. (Switching
embedders self-heals: mismatched-dimension rows are ignored, not compared as
garbage — re-write or re-seed to repopulate.)

## 4. Privacy — sensitive scopes stay on-box

Any scope whose name contains `private/health/finance/legal/hr/...` (or is listed
in `Settings.sensitive_scopes`) is treated as sensitive: it's forced to a local
model, and its memory is never packed into a prompt bound for a cloud model.
Write secrets under such a scope:

```
:scope health-private
I take 10mg of X daily.
```

## 5. Other backends / interfaces

| Want | Install | How |
|---|---|---|
| Hybrid Mem0 semantic store | `.[mem0]` | set `Settings.semantic_backend = "mem0"` |
| GEPA prompt optimization | `.[dspy]` | used by `improvement/gepa_optimizer.py` |
| Nightly consolidation (cron) | `.[schedule]` | APScheduler; stdlib timer otherwise |
| HTTP API | `.[serve]` | `AGI_INTERFACE=api python main.py` → localhost:8765 |
| MCP bridge (share with other agents) | `.[serve]` | `AGI_INTERFACE=mcp python main.py` |

## 6. Config

Edit `config/settings.py` (or wire env): `embedding_model`, `user_name` (greets
you by name), `sensitive_scopes`, `semantic_backend`, retrieval budget/half-life.
Models live in `config/models.yaml`. Env vars: `AGI_INTERFACE`, `AGI_LOG_LEVEL`,
`AGI_DEBUG` (see `.env.example`).
