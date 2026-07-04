"""Background scheduler — runs a job (consolidation) off the hot path.

Uses APScheduler with a cron trigger when installed; otherwise falls back to a
stdlib threading.Timer loop at a fixed interval. `start()` is non-blocking;
`run_now()` triggers the job immediately (manual runs / tests). Never raises — a
scheduler failure must not take down the app.
"""
from __future__ import annotations

import threading


class Scheduler:
    def __init__(self, func, cron: str = "0 3 * * *", interval_seconds: float = 86400.0):
        self.func = func
        self.cron = cron
        self.interval = interval_seconds
        self._sched = None      # APScheduler instance, if used
        self._timer = None      # threading.Timer, fallback
        self._stopped = False

    def start(self) -> str:
        """Start the background job; returns the backend used ('apscheduler' or
        'timer')."""
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
            self._sched = BackgroundScheduler(daemon=True)
            self._sched.add_job(self._safe_run, CronTrigger.from_crontab(self.cron))
            self._sched.start()
            return "apscheduler"
        except Exception:
            self._sched = None
            self._schedule_timer()
            return "timer"

    def run_now(self):
        """Trigger the job immediately (synchronous)."""
        return self._safe_run()

    def stop(self) -> None:
        self._stopped = True
        if self._sched is not None:
            try:
                self._sched.shutdown(wait=False)
            except Exception:
                pass
        if self._timer is not None:
            try:
                self._timer.cancel()
            except Exception:
                pass

    # --- internals ----------------------------------------------------------
    def _schedule_timer(self) -> None:
        if self._stopped:
            return
        self._timer = threading.Timer(self.interval, self._timer_tick)
        self._timer.daemon = True
        self._timer.start()

    def _timer_tick(self) -> None:
        self._safe_run()
        self._schedule_timer()  # reschedule the next tick

    def _safe_run(self):
        try:
            return self.func()
        except Exception:
            return None
