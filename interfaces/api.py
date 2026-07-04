"""Local HTTP API — how apps and agents reach the layer. Bound to localhost.

Run:  AGI_INTERFACE=api python main.py     (needs `pip install fastapi uvicorn`)
Routes:
  POST /turn         {input, scope}  -> {reply}
  GET  /memory       ?query&scope    -> {items, dropped}
  POST /consolidate  trigger the sleep pass
"""
from __future__ import annotations

from core.session import Session


def build_app(orchestrator, store=None):
    try:
        from fastapi import FastAPI
        from pydantic import BaseModel
    except Exception as e:  # pragma: no cover - depends on install
        raise RuntimeError(
            "FastAPI isn't installed — `pip install fastapi uvicorn` to run the API."
        ) from e

    store = store or orchestrator.memory
    app = FastAPI(title="agi-layer")

    class TurnIn(BaseModel):
        input: str
        scope: str | None = None

    @app.post("/turn")
    def turn(body: TurnIn):
        return {"reply": orchestrator.handle_turn(body.input, Session(scope=body.scope))}

    @app.get("/memory")
    def memory(query: str, scope: str | None = None, budget_tokens: int = 2000):
        bundle = store.retrieve(query, scope=scope, budget_tokens=budget_tokens)
        return {"items": [c.content for c in bundle.items],
                "dropped": bundle.summary_of_dropped}

    @app.post("/consolidate")
    def consolidate():
        store.consolidate()
        return {"status": "ok"}

    return app


def serve(app, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Serve on localhost (local-first). Requires uvicorn."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)
