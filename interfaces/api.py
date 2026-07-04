"""Local HTTP / websocket API — how apps and agents reach the layer."""
from __future__ import annotations

# from fastapi import FastAPI
#
# Wire routes to the orchestrator:
#   POST /turn         {input, scope} -> {reply}
#   GET  /memory       search / inspect memory
#   POST /consolidate  trigger consolidation manually
#
# Keep it bound to localhost — the whole point is local-first privacy.


def build_app(orchestrator):
    raise NotImplementedError("Wire FastAPI routes; see ARCHITECTURE.md (Interfaces)")
