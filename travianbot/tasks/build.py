"""Upgrade buildings / resource fields from a configured queue."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from playwright.sync_api import Error as PlaywrightError, Locator

from ..browser import TravianSession
from .base import Task, TaskResult, parse_int, register, switch_village

log = logging.getLogger(__name__)


@register
class BuildTask(Task):
    """options:
        village: nazov alebo poradie dediny (nepovinne)
        queue:   zoznam poloh na vylepsenie, napr.
                 - 1                      # policko c. 1
                 - {slot: 26, max_level: 20}
                 - {slot: 19, gid: 19}    # kasarne
        upgrades_per_run: kolko vylepseni max. spustit v jednom behu (default 1)
    """

    type_name = "build"

    def execute(self, session: TravianSession) -> TaskResult:
        village = switch_village(session, self.opt("village"))
        queue = self._normalize_queue(self.opt("queue") or [])
        if not queue:
            return TaskResult.skipped("Prazdna fronta stavania (options.queue).")

        limit = max(1, int(self.opt("upgrades_per_run", 1)))
        started: List[str] = []
        blocked: List[str] = []

        for entry in queue:
            if len(started) >= limit:
                break
            outcome = self._try_upgrade(session, entry)
            if outcome is True:
                started.append(f"slot {entry['slot']}")
            elif outcome is False:
                blocked.append(f"slot {entry['slot']}")

        where = f" [{village.name}]" if village else ""
        if started:
            return TaskResult.success(
                f"Spustene vylepsenie: {', '.join(started)}{where}", started=started, blocked=blocked
            )
        if blocked:
            return TaskResult.skipped(
                f"Nic sa nedalo postavit (suroviny / plna fronta): {', '.join(blocked)}{where}",
                blocked=blocked,
            )
        return TaskResult.skipped(f"Vsetky polozky vo fronte su hotove alebo nedostupne{where}.")

    # ------------------------------------------------------------------ #
    def _normalize_queue(self, raw: Any) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        if isinstance(raw, (int, str)):
            raw = [raw]
        for item in raw:
            if isinstance(item, dict):
                if "slot" not in item:
                    log.warning("Polozka fronty bez 'slot' preskocena: %s", item)
                    continue
                entries.append(dict(item))
            else:
                entries.append({"slot": int(item)})
        return entries

    def _try_upgrade(self, session: TravianSession, entry: Dict[str, Any]) -> Optional[bool]:
        """True = upgrade started, False = blocked, None = nothing to do."""
        slot = int(entry["slot"])
        gid = entry.get("gid")
        path = f"/build.php?id={slot}" + (f"&gid={int(gid)}" if gid else "")
        try:
            session.goto(path)
        except PlaywrightError as exc:
            log.warning("Slot %s sa nepodarilo otvorit: %s", slot, exc)
            return None

        max_level = entry.get("max_level")
        if max_level is not None:
            level = parse_int(session.text_of("build_level_text"))
            if level is not None and level >= int(max_level):
                log.info("Slot %s uz ma uroven %s (max %s) - preskakujem.", slot, level, max_level)
                return None

        button = session.find("build_upgrade_button", timeout_ms=3000)
        if button is None:
            return None
        if not self._is_clickable(button):
            return False
        if session.click_element(button):
            log.info("Spustene vylepsenie slotu %s.", slot)
            return True
        return False

    @staticmethod
    def _is_clickable(element: Locator) -> bool:
        try:
            if not element.is_enabled(timeout=2000):
                return False
            classes = (element.get_attribute("class", timeout=2000) or "").lower()
        except PlaywrightError:
            return False
        return not any(flag in classes for flag in ("disabled", "gray", "grey", "notnow"))
