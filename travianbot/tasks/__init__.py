"""Task package - importing it registers every built-in task type."""

from __future__ import annotations

from .base import Task, TaskResult, create_task, known_types, register  # noqa: F401
from . import adventure, build, farmlist, keepalive, train  # noqa: F401

__all__ = ["Task", "TaskResult", "create_task", "known_types", "register"]
