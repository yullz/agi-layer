"""User profile helpers — turn free-text onboarding answers into a timezone and
a working-hours window, so scheduled routines line up with the user's day.

Everything is best-effort and dependency-free: a location string becomes a
`tzinfo` (IANA via zoneinfo when available, else a fixed UTC offset), and an
hours string becomes ("HH:MM", "HH:MM"). Unparseable input returns None and the
caller falls back to the machine's local time.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:                       # pragma: no cover
    ZoneInfo = None

# city / abbreviation -> (IANA name, fallback fixed offset in hours)
_CITY_TZ = {
    "utc": ("UTC", 0), "gmt": ("UTC", 0),
    "london": ("Europe/London", 0), "dublin": ("Europe/Dublin", 0),
    "lisbon": ("Europe/Lisbon", 0), "wet": ("Europe/Lisbon", 0),
    "berlin": ("Europe/Berlin", 1), "cet": ("Europe/Berlin", 1),
    "paris": ("Europe/Paris", 1), "madrid": ("Europe/Madrid", 1),
    "amsterdam": ("Europe/Amsterdam", 1), "rome": ("Europe/Rome", 1),
    "vienna": ("Europe/Vienna", 1), "zurich": ("Europe/Zurich", 1),
    "sofia": ("Europe/Sofia", 2), "athens": ("Europe/Athens", 2),
    "helsinki": ("Europe/Helsinki", 2), "eet": ("Europe/Sofia", 2),
    "kyiv": ("Europe/Kyiv", 2), "kiev": ("Europe/Kyiv", 2),
    "moscow": ("Europe/Moscow", 3), "istanbul": ("Europe/Istanbul", 3),
    "dubai": ("Asia/Dubai", 4),
    "karachi": ("Asia/Karachi", 5),
    "mumbai": ("Asia/Kolkata", 5), "delhi": ("Asia/Kolkata", 5),
    "bangalore": ("Asia/Kolkata", 5), "ist": ("Asia/Kolkata", 5),
    "dhaka": ("Asia/Dhaka", 6), "bangkok": ("Asia/Bangkok", 7),
    "singapore": ("Asia/Singapore", 8), "shanghai": ("Asia/Shanghai", 8),
    "beijing": ("Asia/Shanghai", 8), "hong kong": ("Asia/Hong_Kong", 8),
    "tokyo": ("Asia/Tokyo", 9), "jst": ("Asia/Tokyo", 9), "seoul": ("Asia/Seoul", 9),
    "sydney": ("Australia/Sydney", 10), "melbourne": ("Australia/Melbourne", 10),
    "auckland": ("Pacific/Auckland", 12),
    "new york": ("America/New_York", -5), "nyc": ("America/New_York", -5),
    "est": ("America/New_York", -5), "edt": ("America/New_York", -4),
    "boston": ("America/New_York", -5), "toronto": ("America/Toronto", -5),
    "chicago": ("America/Chicago", -6), "cst": ("America/Chicago", -6),
    "austin": ("America/Chicago", -6), "dallas": ("America/Chicago", -6),
    "denver": ("America/Denver", -7), "mst": ("America/Denver", -7),
    "los angeles": ("America/Los_Angeles", -8), "san francisco": ("America/Los_Angeles", -8),
    "seattle": ("America/Los_Angeles", -8), "pst": ("America/Los_Angeles", -8),
    "pdt": ("America/Los_Angeles", -7),
    "sao paulo": ("America/Sao_Paulo", -3),
}

_HOUR_WORDS = {
    "morning": ("08:00", "12:00"), "mornings": ("08:00", "12:00"),
    "afternoon": ("12:00", "17:00"), "afternoons": ("12:00", "17:00"),
    "evening": ("17:00", "21:00"), "evenings": ("17:00", "21:00"),
    "night": ("21:00", "23:59"), "nights": ("21:00", "23:59"),
    "nine to five": ("09:00", "17:00"),
}


def _fixed(offset_hours: float):
    return timezone(timedelta(hours=offset_hours))


def _zone(iana: str, offset: float):
    if ZoneInfo is not None:
        try:
            return ZoneInfo(iana)
        except Exception:
            pass
    return _fixed(offset)


def parse_timezone(text):
    """Free-text location/timezone -> tzinfo, or None if unrecognizable."""
    if not text:
        return None
    s = str(text).strip()
    low = s.lower()
    if low in ("utc", "gmt"):
        return _fixed(0)
    if "/" in s and ZoneInfo is not None:            # explicit IANA name
        try:
            return ZoneInfo(s)
        except Exception:
            pass
    m = re.search(r"(utc|gmt)?\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?", low)
    if m and (m.group(1) or low[:1] in "+-"):        # a UTC/GMT offset
        sign = 1 if m.group(2) == "+" else -1
        return _fixed(sign * (int(m.group(3)) + int(m.group(4) or 0) / 60.0))
    for key, (iana, off) in _CITY_TZ.items():        # a city / abbreviation
        if re.search(r"\b" + re.escape(key) + r"\b", low):
            return _zone(iana, off)
    return None


def _to_hm(tok):
    h = int(tok[0])
    mi = int(tok[1] or 0)
    ap = tok[2]
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if h == 24:
        h = 0
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    return f"{h:02d}:{mi:02d}"


def parse_working_hours(text):
    """Free-text hours -> ("HH:MM", "HH:MM") start/end, or None."""
    if not text:
        return None
    s = str(text).lower().strip()
    for word, span in _HOUR_WORDS.items():
        if re.search(r"\b" + word + r"\b", s):
            return span
    if re.search(r"\b9\s*(?:to|-|–)\s*5\b", s):
        return ("09:00", "17:00")
    toks = [t for t in re.findall(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", s) if t[0]]
    if len(toks) >= 2:
        start, end = _to_hm(toks[0]), _to_hm(toks[1])
        if start and end:
            return (start, end)
    return None


def derive(answers: dict) -> dict:
    """From onboarding answers ({key: text}), derive a persistable profile with
    a timezone (kept as the raw string so it re-parses) and working hours."""
    out = {}
    loc = (answers or {}).get("location")
    if loc and parse_timezone(loc) is not None:
        out["timezone"] = loc
    wh = parse_working_hours((answers or {}).get("hours"))
    if wh:
        out["work_start"], out["work_end"] = wh
    return out


# --- clock helpers (tz-aware) -----------------------------------------------
def _dt(tz, ts):
    return datetime.fromtimestamp(ts, tz) if tz else datetime.fromtimestamp(ts)


def now_hhmm(tz, ts) -> str:
    d = _dt(tz, ts)
    return f"{d.hour:02d}:{d.minute:02d}"


def day_key(tz, ts) -> str:
    d = _dt(tz, ts)
    return f"{d.year}-{d.timetuple().tm_yday}"


def tz_label(tz) -> str:
    if tz is None:
        return "system local"
    return str(getattr(tz, "key", None) or tz)
