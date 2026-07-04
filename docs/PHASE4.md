# Phase 4 — The bridge (MCP + HTTP interfaces)

(Recorded after the fact — this phase shipped with Phase 3 in one PR.)

What makes agi-layer *the bridge* between your AIs rather than just another
assistant: it exposes its memory + routing so other agents connect to it as a
shared hub.

- **`interfaces/mcp.py`** — `build_mcp_server(store, orchestrator)` publishes
  three MCP tools:
  - `ask(input, scope)` — route a message through the full turn loop.
  - `retrieve_memory(query, scope)` — read-only memory search.
  - `remember(fact, scope)` — write a durable memory item.
  Run with `AGI_INTERFACE=mcp python main.py` (needs `pip install -e ".[serve]"`).
- **`interfaces/api.py`** — `build_app(orchestrator)` serves a localhost HTTP API:
  `POST /turn`, `GET /memory`, `POST /consolidate`. Run with
  `AGI_INTERFACE=api python main.py`.
- **`main.py`** selects the interface via `AGI_INTERFACE` (`cli` default | `api`
  | `mcp`). Both interface modules import-guard their SDKs, so the layer always
  boots even when they're not installed.

Note: the MCP/HTTP surfaces are local-first and currently unauthenticated — see
`docs/REVIEW.md` for the planned local-token + per-scope allow-list hardening
before exposing them beyond localhost.
