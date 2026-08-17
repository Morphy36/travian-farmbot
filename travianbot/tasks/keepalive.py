"""Cheap task that just loads a couple of pages so the session stays alive
(and the activity pattern looks less like 'log in, raid, log out')."""

from __future__ import annotations

import random

from ..browser import TravianSession
from ..selectors import PATHS
from .base import Task, TaskResult, register


@register
class KeepAliveTask(Task):
    """options:
        pages: zoznam ciest (default dorf1 + dorf2)
    """

    type_name = "keepalive"

    def execute(self, session: TravianSession) -> TaskResult:
        pages = self.opt("pages") or [PATHS["dorf1"][0], PATHS["dorf2"][0]]
        if isinstance(pages, str):
            pages = [pages]
        visited = 0
        for path in random.sample(list(pages), k=len(pages)):
            session.goto(str(path))
            try:
                session.page.mouse.wheel(0, random.randint(120, 600))
            except Exception:  # noqa: BLE001 - purely cosmetic
                pass
            session.pause()
            visited += 1
        return TaskResult.success(f"Session obnovena ({visited} stranok)", visited=visited)


@register
class ScreenshotTask(Task):
    """Debug: ulozi screenshot + HTML zadanej stranky do data/debug.

    options:
        path: cesta na serveri (default /dorf1.php)
        label: nazov suboru
    """

    type_name = "screenshot"

    def execute(self, session: TravianSession) -> TaskResult:
        path = str(self.opt("path", PATHS["dorf1"][0]))
        session.goto(path)
        saved = session.dump(str(self.opt("label", "screenshot")))
        if saved is None:
            return TaskResult.failure("Screenshot sa nepodarilo ulozit.")
        return TaskResult.success(f"Ulozene: {saved.name}", file=str(saved))
