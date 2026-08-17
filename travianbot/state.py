"""Thread-safe runtime state, shared between the scheduler, the worker and the
web dashboard."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat(timespec="seconds") if value else None


@dataclass
class TaskStatus:
    name: str
    type: str
    enabled: bool
    schedule_text: str
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    last_ok: Optional[bool] = None
    last_message: str = ""
    runs: int = 0
    failures: int = 0
    running: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "enabled": self.enabled,
            "schedule_text": self.schedule_text,
            "next_run": _iso(self.next_run),
            "last_run": _iso(self.last_run),
            "last_ok": self.last_ok,
            "last_message": self.last_message,
            "runs": self.runs,
            "failures": self.failures,
            "running": self.running,
        }


class BotState:
    def __init__(self, history_size: int = 100):
        self._lock = threading.RLock()
        self.started_at = datetime.now()
        self.paused = False
        self.pause_reason = ""
        self.consecutive_failures = 0
        self.tasks: Dict[str, TaskStatus] = {}
        self.history: Deque[Dict[str, Any]] = deque(maxlen=history_size)

    # ------------------------------------------------------------------ #
    def register_task(self, status: TaskStatus) -> None:
        with self._lock:
            self.tasks[status.name] = status

    def update_task(self, name: str, **fields: Any) -> None:
        with self._lock:
            status = self.tasks.get(name)
            if status is None:
                return
            for key, value in fields.items():
                setattr(status, key, value)

    def record_run(self, name: str, ok: bool, message: str, when: Optional[datetime] = None) -> None:
        when = when or datetime.now()
        with self._lock:
            status = self.tasks.get(name)
            if status is not None:
                status.last_run = when
                status.last_ok = ok
                status.last_message = message
                status.runs += 1
                if not ok:
                    status.failures += 1
            self.consecutive_failures = 0 if ok else self.consecutive_failures + 1
            self.history.appendleft(
                {"time": _iso(when), "task": name, "ok": ok, "message": message}
            )

    def set_paused(self, paused: bool, reason: str = "") -> None:
        with self._lock:
            self.paused = paused
            self.pause_reason = reason if paused else ""

    def set_enabled(self, name: str, enabled: bool) -> None:
        with self._lock:
            status = self.tasks.get(name)
            if status is not None:
                status.enabled = enabled

    def is_enabled(self, name: str) -> bool:
        with self._lock:
            status = self.tasks.get(name)
            return bool(status and status.enabled)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "started_at": _iso(self.started_at),
                "now": _iso(datetime.now()),
                "paused": self.paused,
                "pause_reason": self.pause_reason,
                "consecutive_failures": self.consecutive_failures,
                "tasks": [task.to_dict() for task in self.tasks.values()],
                "history": list(self.history)[:40],
            }

    def task_names(self) -> List[str]:
        with self._lock:
            return list(self.tasks)
