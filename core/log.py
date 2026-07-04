"""Project logger — one place to make silent failures observable.

Use `from core.log import log`. Level via the AGI_LOG_LEVEL env var
(default WARNING). Best-effort swallows on background paths should log at
warning with exc_info so a dropped fact/edge leaves a trace instead of vanishing.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger("agi")

if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s agi: %(message)s"))
    log.addHandler(_h)
    log.setLevel(getattr(logging, os.environ.get("AGI_LOG_LEVEL", "WARNING").upper(), logging.WARNING))
    log.propagate = False
