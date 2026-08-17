"""Playwright session wrapper: one persistent Chromium profile, login handling
and a few helpers that all tasks share."""

from __future__ import annotations

import logging
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from playwright.sync_api import (
    BrowserContext,
    Error as PlaywrightError,
    Locator,
    Page,
    TimeoutError as PlaywrightTimeout,
    sync_playwright,
)

from .config import Config
from .selectors import PATHS, build_selectors
from .utils import human_pause

log = logging.getLogger(__name__)


class LoginFailed(Exception):
    """Raised when the bot cannot get into the game."""


class TravianSession:
    """Owns the browser. Not thread-safe on purpose - only the task worker
    thread is allowed to touch it."""

    def __init__(self, config: Config):
        self.config = config
        self.selectors = build_selectors(config.selectors)
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    @property
    def started(self) -> bool:
        return self._context is not None

    def start(self) -> None:
        if self.started:
            return
        cfg = self.config.browser
        profile_dir = self.config.resolve(cfg.profile_dir)
        profile_dir.mkdir(parents=True, exist_ok=True)

        log.info("Spustam prehliadac (profil: %s, headless=%s)", profile_dir, cfg.headless)
        self._playwright = sync_playwright().start()
        launch_kwargs = dict(
            user_data_dir=str(profile_dir),
            headless=cfg.headless,
            slow_mo=cfg.slow_mo_ms or 0,
            locale=cfg.locale,
            viewport={"width": cfg.viewport_width, "height": cfg.viewport_height},
            args=["--disable-blink-features=AutomationControlled"],
        )
        if cfg.user_agent:
            launch_kwargs["user_agent"] = cfg.user_agent
        self._context = self._playwright.chromium.launch_persistent_context(**launch_kwargs)
        self._context.set_default_timeout(cfg.timeout_ms)
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()

    def stop(self) -> None:
        if self._context is not None:
            try:
                self._context.close()
            except Exception:  # noqa: BLE001 - closing must never break the loop
                log.debug("Prehliadac sa nepodarilo cisto zavriet.", exc_info=True)
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:  # noqa: BLE001
                log.debug("Playwright sa nepodarilo cisto zastavit.", exc_info=True)
        self._context = None
        self._page = None
        self._playwright = None
        log.info("Prehliadac zatvoreny.")

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Prehliadac nie je spusteny - zavolaj start().")
        return self._page

    # ------------------------------------------------------------------ #
    # navigation & element helpers
    # ------------------------------------------------------------------ #
    def url_for(self, path: str) -> str:
        return f"{self.config.account.server_url}{path}"

    def goto(self, path: str, wait: str = "domcontentloaded") -> None:
        self.page.goto(self.url_for(path), wait_until=wait)
        self.pause()

    def pause(self) -> None:
        """Human-ish delay between two actions."""
        human_pause(self.config.behavior.action_delay)

    def sel(self, key: str) -> List[str]:
        return self.selectors.get(key, [])

    def find(self, key: str, timeout_ms: int = 4000, scope: Optional[Locator] = None) -> Optional[Locator]:
        """Return the first visible element matching any candidate selector for `key`."""
        root = scope if scope is not None else self.page
        deadline_each = max(300, timeout_ms // max(1, len(self.sel(key)) or 1))
        for selector in self.sel(key):
            try:
                locator = root.locator(selector).first
                locator.wait_for(state="visible", timeout=deadline_each)
                return locator
            except (PlaywrightTimeout, PlaywrightError):
                continue
        return None

    def find_all(self, key: str, scope: Optional[Locator] = None) -> List[Locator]:
        """Return all elements for the first candidate selector that matches anything."""
        root = scope if scope is not None else self.page
        for selector in self.sel(key):
            try:
                locator = root.locator(selector)
                count = locator.count()
            except PlaywrightError:
                continue
            if count:
                return [locator.nth(i) for i in range(count)]
        return []

    def click(self, key: str, timeout_ms: int = 4000, scope: Optional[Locator] = None) -> bool:
        element = self.find(key, timeout_ms=timeout_ms, scope=scope)
        if element is None:
            return False
        return self.click_element(element)

    def click_element(self, element: Locator) -> bool:
        try:
            element.scroll_into_view_if_needed(timeout=3000)
        except (PlaywrightTimeout, PlaywrightError):
            pass
        self.pause()
        try:
            element.click(timeout=5000)
        except (PlaywrightTimeout, PlaywrightError) as exc:
            log.debug("Klik zlyhal: %s", exc)
            return False
        self.pause()
        return True

    def fill(self, key: str, value: str, scope: Optional[Locator] = None) -> bool:
        element = self.find(key, scope=scope)
        if element is None:
            return False
        try:
            element.click(timeout=3000)
            element.fill("")
            # type() emits real key events, which looks more natural than fill()
            element.type(value, delay=random.randint(40, 120))
        except (PlaywrightTimeout, PlaywrightError):
            return False
        return True

    def has(self, key: str, timeout_ms: int = 1500) -> bool:
        return self.find(key, timeout_ms=timeout_ms) is not None

    def text_of(self, key: str, scope: Optional[Locator] = None) -> Optional[str]:
        element = self.find(key, scope=scope)
        if element is None:
            return None
        try:
            return (element.inner_text(timeout=3000) or "").strip()
        except (PlaywrightTimeout, PlaywrightError):
            return None

    # ------------------------------------------------------------------ #
    # login
    # ------------------------------------------------------------------ #
    def is_logged_in(self) -> bool:
        return self.has("logged_in_marker", timeout_ms=2500)

    def ensure_logged_in(self) -> None:
        """Make sure we are on a game page with a live session."""
        self.start()
        try:
            current = self.page.url
        except PlaywrightError:
            current = ""
        if not current.startswith(self.config.account.server_url):
            self.goto(PATHS["dorf1"][0])
        if self.is_logged_in():
            return

        log.info("Session neaktivna - prihlasujem sa.")
        self.goto(PATHS["login"][0])
        if self.is_logged_in():
            return

        if not self.fill("login_username", self.config.account.username):
            raise LoginFailed(
                "Nenasiel som pole pre meno. Prihlas sa raz rucne cez 'run.bat --browser' "
                "(prehliadac si session zapamata)."
            )
        if not self.fill("login_password", self.config.account.password):
            raise LoginFailed("Nenasiel som pole pre heslo.")
        if not self.click("login_submit"):
            raise LoginFailed("Nenasiel som tlacidlo na prihlasenie.")

        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=15000)
        except PlaywrightTimeout:
            pass
        self.pause()
        if not self.is_logged_in():
            self.dump("login-failed")
            raise LoginFailed(
                "Prihlasenie zlyhalo. Skontroluj udaje v config.yaml, alebo sa prihlas rucne "
                "cez 'run.bat --browser' (napr. ak server pyta CAPTCHA alebo suhlas s cookies)."
            )
        log.info("Prihlasenie OK.")

    # ------------------------------------------------------------------ #
    # multi-page entry points (some URLs differ between Travian versions)
    # ------------------------------------------------------------------ #
    def open_first_working(self, paths: Iterable[str], marker_key: str) -> bool:
        """Try several URLs until one of them shows `marker_key`."""
        for path in paths:
            try:
                self.goto(path)
            except PlaywrightError as exc:
                log.debug("URL %s zlyhala: %s", path, exc)
                continue
            if self.has(marker_key, timeout_ms=3000):
                return True
        return False

    # ------------------------------------------------------------------ #
    # debugging
    # ------------------------------------------------------------------ #
    def dump(self, label: str) -> Optional[Path]:
        """Save a screenshot + HTML so selectors can be fixed after a game update."""
        if self._page is None:
            return None
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", label)[:60]
        out_dir = self.config.resolve("data/debug")
        out_dir.mkdir(parents=True, exist_ok=True)
        png = out_dir / f"{stamp}-{safe}.png"
        html = out_dir / f"{stamp}-{safe}.html"
        try:
            self._page.screenshot(path=str(png), full_page=True)
            html.write_text(self._page.content(), encoding="utf-8")
            log.info("Ulozeny debug vypis: %s", png)
            return png
        except PlaywrightError:
            log.debug("Debug vypis sa nepodaril.", exc_info=True)
            return None
