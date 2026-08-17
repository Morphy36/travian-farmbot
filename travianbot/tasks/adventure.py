"""Send the hero on adventures when his health is high enough."""

from __future__ import annotations

import logging
import re
from typing import Optional

from ..browser import TravianSession
from ..selectors import PATHS
from .base import Task, TaskResult, register

log = logging.getLogger(__name__)


@register
class AdventureTask(Task):
    """options:
        min_health: minimalne zdravie hrdinu v % (default 35)
        require_health_check: ak true a zdravie sa neda precitat, uloha sa preskoci
    """

    type_name = "adventure"

    def execute(self, session: TravianSession) -> TaskResult:
        min_health = int(self.opt("min_health", 35))
        health = self._read_health(session)

        if health is None and bool(self.opt("require_health_check", True)):
            return TaskResult.skipped("Nepodarilo sa precitat zdravie hrdinu - dobrodruzstvo preskocene.")
        if health is not None and health < min_health:
            return TaskResult.skipped(
                f"Hrdina ma {health}% zdravia (minimum {min_health}%) - necham ho doma.", health=health
            )

        if not session.open_first_working(PATHS["hero_adventures"], "adventure_row"):
            if session.has("adventure_none_marker", timeout_ms=2000):
                return TaskResult.skipped("Ziadne dostupne dobrodruzstva.")
            session.dump("adventures-page-not-found")
            return TaskResult.failure("Nenasiel som zoznam dobrodruzstiev.")

        button = session.find("adventure_start", timeout_ms=4000)
        if button is None:
            return TaskResult.skipped("Ziadne dobrodruzstvo na odoslanie.")
        if not session.click_element(button):
            return TaskResult.failure("Nepodarilo sa kliknut na dobrodruzstvo.")

        # Some versions open a confirmation page with a second button.
        confirm = session.find("adventure_confirm", timeout_ms=3000)
        if confirm is not None:
            session.click_element(confirm)

        log.info("Hrdina vyslany na dobrodruzstvo (zdravie %s%%).", health)
        return TaskResult.success(
            f"Hrdina vyslany na dobrodruzstvo (zdravie {health if health is not None else '?'}%)",
            health=health,
        )

    # ------------------------------------------------------------------ #
    def _read_health(self, session: TravianSession) -> Optional[int]:
        for key in ("hero_health_text",):
            text = session.text_of(key)
            value = self._parse_percent(text)
            if value is not None:
                return value

        # Fall back to the hero attributes page.
        if session.open_first_working(PATHS["hero_attributes"], "hero_health_text"):
            value = self._parse_percent(session.text_of("hero_health_text"))
            if value is not None:
                return value
        return None

    @staticmethod
    def _parse_percent(text: Optional[str]) -> Optional[int]:
        if not text:
            return None
        match = re.search(r"(\d{1,3})\s*%", text)
        if not match:
            match = re.search(r"\d{1,3}", text)
        if not match:
            return None
        value = int(match.group(1) if match.groups() else match.group(0))
        return value if 0 <= value <= 100 else None
