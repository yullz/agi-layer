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
        # First-boot onboarding, mirrored from the terminal so the web app gives
        # the same introductory interview. `_onb` holds the in-progress flow per
        # session (question index + answers); `_onb_seen` marks sessions we've
        # already auto-offered it to, so we don't re-prompt every message.
        self._onb: dict = {}
        self._onb_seen: set = set()
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

        # Onboarding first — same first-boot interview as the terminal. If a flow
        # is in progress this message is an answer; a brand-new user is offered it
        # on their first message; and anyone can ask for it in plain language.
        ob = getattr(self.orch, "onboarding", None)
        if ob is not None:
            if sid in self._onb:
                return self._onb_answer(sess, sid, text, ob)
            if self._wants_onboarding(text):
                return self._onb_start(sess, sid, ob, rerun=ob.is_done())
            if not ob.is_done() and sid not in self._onb_seen:
                return self._onb_start(sess, sid, ob, rerun=False)

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

    # --- onboarding (parity with the terminal's first-boot interview) --------
    _ONB_TRIGGERS = (
        "onboard", "get to know me", "introduction question",
        "introductory question", "intro question", "interview me",
        "ask me the intro", "ask me your questions", "ask me those questions",
        "redo the introduction", "redo introduction", "run the introduction",
    )

    def _wants_onboarding(self, text: str) -> bool:
        t = (text or "").lower()
        return any(k in t for k in self._ONB_TRIGGERS)

    def start_onboarding(self, sid: str = "default") -> dict:
        """Begin (or restart) the introductory interview for this session — the
        button/endpoint the UI can call so it's discoverable, not just typed."""
        ob = getattr(self.orch, "onboarding", None)
        sess = self._session(sid)
        if ob is None:
            return {"reply": "Onboarding isn't available right now.",
                    "steps": [], "model": None, "scope": sess.active_scope}
        return self._onb_start(sess, sid, ob, rerun=ob.is_done())

    def _onb_start(self, sess, sid, ob, rerun: bool) -> dict:
        qs = ob.questions()
        self._onb[sid] = {"i": 0, "answers": {}}
        self._onb_seen.add(sid)
        n = len(qs)
        if rerun:
            intro = (f"Sure — let's (re)do introductions. {n} quick questions; "
                     "type 'skip' to pass one or 'stop' to finish early.")
        else:
            intro = (f"Hi — I'm {self.name}. Before we dive in, can I ask you {n} "
                     "quick questions so I actually know you from the start? "
                     "Type 'skip' to pass any, or 'stop' to finish early.")
        return {"reply": f"{intro}\n\n[1/{n}] {qs[0]['q']}", "steps": [],
                "model": None, "scope": sess.active_scope, "onboarding": True}

    def _onb_answer(self, sess, sid, text, ob) -> dict:
        state = self._onb.get(sid) or {"i": 0, "answers": {}}
        qs = ob.questions()
        i = min(int(state.get("i", 0)), len(qs) - 1)
        q = qs[i]
        if ob.is_stop(text):
            return self._onb_finish(sess, sid, ob)
        if not ob.is_skip(text):
            ans = text.strip()
            state.setdefault("answers", {})[q["key"]] = ans
            ob.record(self.orch.memory, q, ans, scope=None)
            if q["key"] == "name":
                try:
                    self.orch.context_builder.user_name = ans
                except Exception:
                    pass
        state["i"] = i + 1
        self._onb[sid] = state
        if state["i"] >= len(qs):
            return self._onb_finish(sess, sid, ob)
        nxt = qs[state["i"]]
        return {"reply": f"[{state['i'] + 1}/{len(qs)}] {nxt['q']}", "steps": [],
                "model": None, "scope": sess.active_scope, "onboarding": True}

    def _onb_finish(self, sess, sid, ob) -> dict:
        from core.profile import derive, parse_timezone
        state = self._onb.pop(sid, {"answers": {}})
        answers = state.get("answers", {})
        profile = derive(answers)
        if "name" in answers:
            profile["name"] = answers["name"]
        ob.complete(profile)
        tz = parse_timezone(profile.get("timezone")) if profile.get("timezone") else None
        if tz is not None:
            try:
                self.orch.routines.set_tz(tz)
            except Exception:
                pass
        who = profile.get("name") or ob.name()
        hi = f", {who}" if who else ""
        extra = ""
        if tz is not None and profile.get("work_start") and profile.get("work_end"):
            extra = (f" I've noted your timezone and workday "
                     f"({profile['work_start']}–{profile['work_end']}), so anything "
                     "I schedule lands at the right local time.")
        reply = (f"Thanks{hi} — that gives me a great start, and I'll remember all "
                 f"of it.{extra} What would you like to do first?")
        return {"reply": reply, "steps": [], "model": None,
                "scope": sess.active_scope, "onboarding": True}

    # --- status -------------------------------------------------------------
    def status(self, sid: str = "default") -> dict:
        sess = self._session(sid)
        return {"name": self.name, "model": self._model_status(),
                "memory": self._memory_count(), "scope": sess.active_scope,
                "models": list(self._registry_names()), "brain": self._brain()}

    # --- brain preference (local-first vs. auto-route) ----------------------
    def set_brain(self, mode: str) -> dict:
        """'local' keeps everyday chat on the on-box model (private + free);
        'auto' routes to the best available brain (e.g. Claude). Persists."""
        from core import brain
        prefer = str(mode).strip().lower() in ("local", "on", "1", "true", "private")
        policy = getattr(self.orch, "policy", None)
        reg = getattr(getattr(self.orch, "router", None), "registry", None)
        if policy is None or reg is None:
            return {"ok": False}
        eff = brain.apply_preference(policy, reg, prefer)
        data_dir = getattr(self.orch, "data_dir", None)
        if data_dir is not None:
            brain.save_pref(data_dir, eff)
        return {"ok": True, **self._brain()}

    def _brain(self) -> dict:
        """{mode: local|auto, model: <what a general turn would use>, local: bool}."""
        from core import brain
        policy = getattr(self.orch, "policy", None)
        router = getattr(self.orch, "router", None)
        reg = getattr(router, "registry", None)
        mode = "local" if (policy is not None and reg is not None
                           and brain.is_local_preferred(policy, reg)) else "auto"
        picked, local = None, False
        if router is not None:
            try:
                m = router.pick("hello", None)
                picked = getattr(m, "model_name", None) or getattr(m, "name", None)
                local = bool(getattr(m, "is_local", False))
            except Exception:
                pass
        return {"mode": mode, "model": picked, "local": local}

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
