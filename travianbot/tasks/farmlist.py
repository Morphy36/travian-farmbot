"""Send farm lists from the rally point - the core of the farm bot."""

from __future__ import annotations

import logging
from typing import List

from ..browser import TravianSession
from ..selectors import PATHS
from .base import Task, TaskResult, register, switch_village

log = logging.getLogger(__name__)


@register
class FarmListTask(Task):
    """options:
        village: nazov alebo poradie dediny (nepovinne, inak aktualna)
        lists:   ["all"] alebo zoznam nazvov farm listov
        prefer_start_all: true/false - skusit najprv tlacidlo "spustit vsetky"
    """

    type_name = "farmlist"

    def execute(self, session: TravianSession) -> TaskResult:
        switch_village(session, self.opt("village"))

        if not session.open_first_working(PATHS["farmlist"], "farmlist_page_marker"):
            session.dump("farmlist-page-not-found")
            return TaskResult.failure(
                "Nenasiel som stranku s farm listami. Skontroluj, ci mas postaveny zhromazdisko "
                "a pripadne uprav 'selectors.farmlist_page_marker' v config.yaml."
            )

        wanted = self.opt("lists") or ["all"]
        if isinstance(wanted, str):
            wanted = [wanted]
        send_all = any(str(item).strip().lower() in ("all", "vsetky", "*") for item in wanted)

        if send_all and self.opt("prefer_start_all", True):
            if session.click("farmlist_start_all", timeout_ms=3000):
                log.info("Spustene vsetky farm listy jednym tlacidlom.")
                return TaskResult.success("Spustene vsetky farm listy", mode="start_all")

        buttons = session.find_all("farmlist_start_one")
        if not buttons:
            session.dump("farmlist-no-buttons")
            return TaskResult.failure(
                "Na stranke nie su ziadne tlacidla na odoslanie farm listu "
                "(alebo sa zmenili selektory hry)."
            )

        if send_all:
            sent = self._click_all(session, buttons)
            if sent == 0:
                return TaskResult.failure("Ziadny farm list sa nepodarilo odoslat.")
            return TaskResult.success(f"Odoslanych farm listov: {sent}", sent=sent)

        return self._send_named(session, [str(x) for x in wanted])

    # ------------------------------------------------------------------ #
    def _click_all(self, session: TravianSession, buttons: List) -> int:
        sent = 0
        for button in buttons:
            try:
                if not button.is_visible():
                    continue
            except Exception:  # noqa: BLE001 - element may vanish after a click
                continue
            if session.click_element(button):
                sent += 1
        log.info("Odoslanych farm listov: %s", sent)
        return sent

    def _send_named(self, session: TravianSession, names: List[str]) -> TaskResult:
        containers = session.find_all("farmlist_container")
        if not containers:
            return TaskResult.failure("Nenasiel som kontajnery farm listov pre vyber podla nazvu.")

        wanted = {name.strip().lower() for name in names}
        sent: List[str] = []
        missed: List[str] = []

        for container in containers:
            try:
                label = (container.inner_text(timeout=2000) or "").strip().lower()
            except Exception:  # noqa: BLE001
                continue
            match = next((name for name in wanted if name in label), None)
            if match is None:
                continue
            button = session.find("farmlist_start_one", timeout_ms=2000, scope=container)
            if button is not None and session.click_element(button):
                sent.append(match)

        missed = sorted(wanted - set(sent))
        if not sent:
            return TaskResult.failure(f"Ziadny z farm listov sa neodoslal: {', '.join(sorted(wanted))}")
        message = f"Odoslane farm listy: {', '.join(sent)}"
        if missed:
            message += f" | neodoslane: {', '.join(missed)}"
        return TaskResult.success(message, sent=sent, missed=missed)
