"""Web app backend — pure handlers behind the browser chat app.

No web framework here: every method returns plain JSON-able dicts, so the app's
logic runs (and is tested) without FastAPI. interfaces/api.py is the thin HTTP
glue that maps routes to these and serves the page. Everything is local — the
browser talks to this over localhost only.
"""
from __future__ import annotations

import time

from core.session import Session
from memory.schema import Role, Source


def _short(text, limit: int = 140) -> str:
    text = str(text).replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _fmt_args(args) -> str:
    return ", ".join(f"{k}={_short(v, 60)}" for k, v in (args or {}).items())


class WebApp:
    def __init__(self, orchestrator):
        self.orch = orchestrator
        self._sessions: dict = {}
        cb = getattr(orchestrator, "context_builder", None)
        self.name = getattr(cb, "assistant_name", "Myro") or "Myro"

    # --- sessions -----------------------------------------------------------
    def _session(self, sid: str, scope=None) -> Session:
        s = self._sessions.get(sid)
        if s is None:
            s = Session(scope=scope)
            self._sessions[sid] = s
        elif scope is not None and scope != s.active_scope:
            s.set_scope(scope or None)
        return s

    # --- chat ---------------------------------------------------------------
    def chat(self, text: str, sid: str = "default", scope=None,
             allow_actions: bool = True) -> dict:
        text = (text or "").strip()
        if not text:
            return {"reply": "", "steps": [], "model": None, "scope": scope}
        sess = self._session(sid, scope)
        confirm = (lambda *_a: True) if allow_actions else None
        try:
            reply = self.orch.handle_turn(text, sess, confirm=confirm)
        except Exception:
            reply = "Sorry — something went wrong on my side. Try again?"
        steps = [{"tool": s.get("tool"), "args": _fmt_args(s.get("args")),
                  "result": _short(s.get("result"), 200),
                  "denied": "denied" in str(s.get("result", "")).lower()}
                 for s in (getattr(self.orch, "last_steps", None) or [])]
        return {"reply": reply, "steps": steps,
                "model": self._last_model(sess), "scope": sess.active_scope}

    def _last_model(self, session):
        for m in reversed(getattr(session, "messages", [])):
            role = m.role.value if isinstance(m.role, Role) else m.role
            if role == "assistant":
                mn = getattr(m, "model", None)
                return None if not mn else ("echo · offline" if mn == "echo" else mn)
        return None

    # --- status -------------------------------------------------------------
    def status(self, sid: str = "default") -> dict:
        sess = self._session(sid)
        return {"name": self.name, "model": self._model_status(),
                "memory": self._memory_count(), "scope": sess.active_scope,
                "models": list(self._registry_names())}

    def _registry_names(self):
        reg = getattr(getattr(self.orch, "router", None), "registry", None)
        return reg.names() if reg else []

    def _model_status(self) -> str:
        reg = getattr(getattr(self.orch, "router", None), "registry", None)
        if reg is None:
            return "echo · offline"
        for name in reg.names():
            if name == "echo":
                continue
            probe = getattr(reg.get(name), "available", None)
            try:
                if callable(probe) and probe():
                    return name
            except Exception:
                continue
        return "echo · offline"

    def _memory_count(self) -> int:
        sem = getattr(self.orch.memory, "semantic", None)
        fn = getattr(sem, "count_all", None) or getattr(sem, "count_current", None)
        try:
            return fn() if fn else 0
        except Exception:
            return 0

    # --- memory -------------------------------------------------------------
    def memory(self, query: str = "", scope=None) -> dict:
        bundle = self.orch.memory.retrieve(query or "", scope=scope, budget_tokens=1800)
        durable = [c for c in bundle.items if c.source in (Source.VECTOR, Source.GRAPH)]
        return {"items": [c.content for c in durable[:20]]}

    def remember(self, fact: str, scope=None) -> dict:
        self.orch.memory.remember((fact or "").strip(), scope=scope)
        return {"ok": True}

    def forget(self, text: str, scope=None) -> dict:
        return {"forgot": int(self.orch.memory.forget((text or "").strip(), scope=scope))}

    # --- profile ------------------------------------------------------------
    def profile(self) -> dict:
        from core.profile import now_hhmm, parse_timezone, tz_label
        ob = getattr(self.orch, "onboarding", None)
        tzs = ob.timezone() if ob else None
        tz = parse_timezone(tzs) if tzs else None
        return {"name": (ob.name() if ob else None),
                "timezone": tz_label(tz), "local_time": now_hhmm(tz, time.time()),
                "work_start": (ob.work_start() if ob else None),
                "work_end": (ob.work_end() if ob else None),
                "model": self._model_status()}

    def set_profile(self, name=None, timezone=None, hours=None) -> dict:
        from core.profile import parse_timezone, parse_working_hours
        ob = getattr(self.orch, "onboarding", None)
        if ob is None:
            return {"ok": False}
        patch = {}
        if name:
            patch["name"] = name
            try:
                self.orch.context_builder.user_name = name
            except Exception:
                pass
        if timezone:
            tz = parse_timezone(timezone)
            if tz is not None:
                patch["timezone"] = timezone
                try:
                    self.orch.routines.set_tz(tz)
                except Exception:
                    pass
        if hours:
            wh = parse_working_hours(hours)
            if wh:
                patch["work_start"], patch["work_end"] = wh
        if patch:
            ob.complete(patch)
        return {"ok": True, **self.profile()}

    # --- connectors / tools -------------------------------------------------
    def connectors(self) -> dict:
        from core.connectors import connector_status
        conf = getattr(self.orch, "connectors", None)
        return {"status": connector_status(conf) if conf is not None else {}}

    def tools(self) -> dict:
        specs = self.orch.tools.specs() if getattr(self.orch, "tools", None) else []
        return {"tools": [{"name": s["name"], "args": s["args"],
                           "gated": not s["unattended"], "description": s["description"]}
                          for s in specs]}

    # --- routines -----------------------------------------------------------
    def routines(self) -> dict:
        from core.routines import describe_schedule
        r = getattr(self.orch, "routines", None)
        items = r.list() if r else {}
        return {"routines": [{"name": n, "task": it.get("task", ""),
                              "scope": it.get("scope"), "schedule": describe_schedule(it),
                              "last": _short(it.get("last_result", ""), 120)}
                             for n, it in items.items()]}

    def add_routine(self, name: str, task: str, scope=None) -> dict:
        r = getattr(self.orch, "routines", None)
        if not (r and name and task):
            return {"ok": False}
        r.add(name.strip(), task.strip(), scope=scope)
        return {"ok": True}

    def run_routine(self, name: str) -> dict:
        r = getattr(self.orch, "routines", None)
        res = r.run(name) if r else {"status": "unavailable"}
        return {"status": res.get("status"), "answer": _short(res.get("answer", ""), 400)}

    def schedule_routine(self, name: str, spec: str) -> dict:
        from interfaces.cli import _apply_schedule, _resolve_workday
        r = getattr(self.orch, "routines", None)
        if not r:
            return {"ok": False, "message": "routines unavailable"}
        rest = _resolve_workday(f"{name} {spec}".strip(), getattr(self.orch, "onboarding", None))
        ok, msg = _apply_schedule(r, rest)
        return {"ok": ok, "message": msg}

    def install_starters(self) -> dict:
        from core.starter_routines import install_starters
        r = getattr(self.orch, "routines", None)
        return {"added": install_starters(r) if r else []}

    # --- backup -------------------------------------------------------------
    def backup(self) -> dict:
        from core import backup as bk
        cfg = getattr(self.orch, "backup_config", None)
        if cfg is None:
            return {"ok": False, "message": "backups unavailable"}
        return {"ok": True, "message": bk.summary(bk.run_backup(cfg))}
