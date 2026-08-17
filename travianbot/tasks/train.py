"""Train troops in barracks / stable / workshop."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from playwright.sync_api import Error as PlaywrightError

from ..browser import TravianSession
from .base import Task, TaskResult, register, switch_village

log = logging.getLogger(__name__)


@register
class TrainTask(Task):
    """options:
        village: nazov alebo poradie dediny (nepovinne)
        slot:    cislo policka s budovou (napr. kasarne)
        gid:     nepovinne (19 = kasarne, 20 = staj, 21 = dielna)
        units:   {t1: max} alebo [{unit: t1, amount: 10}, ...]
    """

    type_name = "train"

    def execute(self, session: TravianSession) -> TaskResult:
        slot = self.opt("slot")
        if slot is None:
            return TaskResult.failure("Chyba 'slot' - cislo policka s budovou (options.slot).")

        units = self._normalize_units(self.opt("units") or {})
        if not units:
            return TaskResult.skipped("Nie su zadane ziadne jednotky (options.units).")

        village = switch_village(session, self.opt("village"))
        gid = self.opt("gid")
        path = f"/build.php?id={int(slot)}" + (f"&gid={int(gid)}" if gid else "")
        session.goto(path)

        filled: List[str] = []
        for unit in units:
            if self._fill_unit(session, unit["unit"], unit["amount"]):
                filled.append(f"{unit['unit']}={unit['amount']}")

        if not filled:
            session.dump("train-no-inputs")
            return TaskResult.skipped("Nenasiel som polia pre zadanie poctu jednotiek.")

        if not session.click("train_submit", timeout_ms=4000):
            return TaskResult.failure("Nenasiel som tlacidlo na spustenie treningu.")

        where = f" [{village.name}]" if village else ""
        log.info("Trening spusteny: %s%s", ", ".join(filled), where)
        return TaskResult.success(f"Trening spusteny: {', '.join(filled)}{where}", units=filled)

    # ------------------------------------------------------------------ #
    def _normalize_units(self, raw: Any) -> List[Dict[str, Any]]:
        units: List[Dict[str, Any]] = []
        if isinstance(raw, dict):
            for key, amount in raw.items():
                units.append({"unit": str(key), "amount": amount})
        else:
            for item in raw:
                if isinstance(item, dict) and "unit" in item:
                    units.append({"unit": str(item["unit"]), "amount": item.get("amount", "max")})
        return units

    def _fill_unit(self, session: TravianSession, unit: str, amount: Any) -> bool:
        selector = f'input[name="{unit}"]'
        try:
            field = session.page.locator(selector).first
            if field.count() == 0:
                return False
        except PlaywrightError:
            return False

        if str(amount).strip().lower() in ("max", "vsetko", "all"):
            row = session.page.locator(f'tr:has({selector})').first
            for max_selector in session.sel("train_max_link"):
                try:
                    link = row.locator(max_selector).first
                    if link.count():
                        link.click(timeout=3000)
                        session.pause()
                        return True
                except PlaywrightError:
                    continue
            log.debug("Odkaz 'max' pre %s sa nenasiel, skusam maximum z popisku.", unit)
            return False

        try:
            field.fill(str(int(amount)), timeout=3000)
        except (PlaywrightError, ValueError):
            return False
        session.pause()
        return True
