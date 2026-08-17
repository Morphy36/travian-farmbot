"""Small helpers shared across the bot: duration parsing, human-like delays,
quiet-hours arithmetic."""

from __future__ import annotations

import random
import re
import time
from datetime import datetime, time as dtime
from typing import Optional, Sequence, Union

_DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)\s*([smhd])", re.IGNORECASE)
_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration(value: Union[str, int, float, None], default: Optional[float] = None) -> float:
    """Parse '20m', '1h30m', '90s', '2d' or a plain number (seconds) to seconds."""
    if value is None:
        if default is None:
            raise ValueError("Chyba hodnota trvania a nie je zadany default.")
        return float(default)
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().lower()
    if not text:
        raise ValueError("Prazdna hodnota trvania.")
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)

    matches = _DURATION_RE.findall(text)
    if not matches:
        raise ValueError(f"Neplatne trvanie: {value!r} (pouzi napr. '20m', '1h30m', '45s').")
    # Make sure the whole string was consumed by the matches, so typos are caught.
    consumed = "".join(f"{num}{unit}" for num, unit in matches)
    if re.sub(r"\s+", "", text) != consumed.lower():
        raise ValueError(f"Neplatne trvanie: {value!r} (pouzi napr. '20m', '1h30m', '45s').")

    return float(sum(float(num) * _UNITS[unit.lower()] for num, unit in matches))


def format_duration(seconds: float) -> str:
    seconds = int(max(0, seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {sec}s" if sec else f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m" if minutes else f"{hours}h"


def parse_hhmm(value: str) -> dtime:
    """Parse 'HH:MM' (or 'H:MM') into a time object."""
    parts = str(value).strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Neplatny cas: {value!r} (ocakavam 'HH:MM').")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Neplatny cas: {value!r}.")
    return dtime(hour=hour, minute=minute)


def in_time_window(now: datetime, start: dtime, end: dtime) -> bool:
    """True if `now` falls inside [start, end); handles windows crossing midnight."""
    current = now.time()
    if start == end:
        return False
    if start < end:
        return start <= current < end
    return current >= start or current < end


def human_pause(delay_range: Sequence[float]) -> None:
    """Sleep a random amount of time (seconds) to look less robotic."""
    low, high = float(delay_range[0]), float(delay_range[1])
    if high < low:
        low, high = high, low
    time.sleep(random.uniform(low, high))


def jittered(seconds: float, jitter_pct: float) -> float:
    """Apply +/- jitter_pct % noise to a number of seconds."""
    if jitter_pct <= 0:
        return seconds
    factor = 1.0 + random.uniform(-jitter_pct, jitter_pct) / 100.0
    return max(1.0, seconds * factor)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
