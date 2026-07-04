"""Local web app + HTTP API — Myro's browser face and machine interface.

Run:  AGI_INTERFACE=api python main.py     (needs `pip install fastapi uvicorn`)
Then open http://127.0.0.1:8765 for the chat app. Everything is bound to
localhost — the browser talks to your own machine, never the internet.

The app's logic lives in interfaces/webapi.py (framework-free, tested offline);
this file is the thin HTTP layer: it serves the page and maps /api/* to those
handlers.
"""
# NOTE: no `from __future__ import annotations` here — FastAPI must see the real
# Pydantic model classes on the endpoint signatures (string annotations would be
# resolved against module globals, where these locally-defined models don't live).
import os

from core.session import Session
from interfaces.webapi import WebApp

_STATIC = os.path.join(os.path.dirname(__file__), "static")


def build_app(orchestrator, store=None):
    try:
        from fastapi import FastAPI
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles
        from pydantic import BaseModel
    except Exception as e:  # pragma: no cover - depends on install
        raise RuntimeError(
            "FastAPI isn't installed — `pip install fastapi uvicorn` to run the app."
        ) from e

    store = store or orchestrator.memory
    web = WebApp(orchestrator)
    app = FastAPI(title="Myro")

    class ChatIn(BaseModel):
        text: str
        sid: str = "default"
        scope: str | None = None
        allow_actions: bool = True

    class Fact(BaseModel):
        fact: str
        scope: str | None = None

    class ProfileIn(BaseModel):
        name: str | None = None
        timezone: str | None = None
        hours: str | None = None

    class RoutineIn(BaseModel):
        name: str
        task: str | None = None
        scope: str | None = None
        spec: str | None = None

    class SidIn(BaseModel):
        sid: str = "default"

    # --- the app page ---
    @app.get("/")
    def index():
        return FileResponse(os.path.join(_STATIC, "index.html"))

    # --- app API (browser <-> Myro) ---
    @app.post("/api/chat")
    def chat(body: ChatIn):
        return web.chat(body.text, sid=body.sid, scope=body.scope,
                        allow_actions=body.allow_actions)

    @app.post("/api/onboarding/start")
    def onboarding_start(body: SidIn):
        return web.start_onboarding(body.sid)

    @app.get("/api/status")
    def status(sid: str = "default"):
        return web.status(sid)

    @app.get("/api/memory")
    def memory_get(q: str = "", scope: str | None = None, sid: str = "default"):
        return web.memory(q, scope=scope)

    @app.post("/api/remember")
    def remember(body: Fact):
        return web.remember(body.fact, scope=body.scope)

    @app.get("/api/profile")
    def profile_get():
        return web.profile()

    @app.post("/api/profile")
    def profile_set(body: ProfileIn):
        return web.set_profile(name=body.name, timezone=body.timezone, hours=body.hours)

    @app.get("/api/connectors")
    def connectors():
        return web.connectors()

    @app.get("/api/tools")
    def tools():
        return web.tools()

    @app.get("/api/routines")
    def routines():
        return web.routines()

    @app.post("/api/routines/add")
    def routine_add(body: RoutineIn):
        return web.add_routine(body.name, body.task or "", scope=body.scope)

    @app.post("/api/routines/run")
    def routine_run(body: RoutineIn):
        return web.run_routine(body.name)

    @app.post("/api/routines/schedule")
    def routine_schedule(body: RoutineIn):
        return web.schedule_routine(body.name, body.spec or "")

    @app.post("/api/starters")
    def starters():
        return web.install_starters()

    @app.post("/api/backup")
    def backup():
        return web.backup()

    # --- back-compat machine API ---
    @app.post("/turn")
    def turn(body: ChatIn):
        return {"reply": orchestrator.handle_turn(body.text, Session(scope=body.scope))}

    @app.get("/memory")
    def memory(query: str, scope: str | None = None, budget_tokens: int = 2000):
        bundle = store.retrieve(query, scope=scope, budget_tokens=budget_tokens)
        return {"items": [c.content for c in bundle.items],
                "dropped": bundle.summary_of_dropped}

    @app.post("/consolidate")
    def consolidate():
        store.consolidate()
        return {"status": "ok"}

    if os.path.isdir(_STATIC):
        app.mount("/static", StaticFiles(directory=_STATIC), name="static")
    return app


def serve(app, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    """Serve on localhost (local-first). Opens the chat app in your browser."""
    import uvicorn
    url = f"http://{host}:{port}"
    if open_browser:
        try:
            import threading
            import webbrowser
            threading.Timer(1.2, lambda: webbrowser.open(url)).start()
        except Exception:
            pass
    print(f"\n  Myro is running — open  {url}  in your browser.\n  (Ctrl-C to stop.)\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")
