"""Optional Telegram notifications (errors, and optionally every run)."""

from __future__ import annotations

import logging
from typing import Optional

import requests

from .config import TelegramConfig

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, config: TelegramConfig):
        self.config = config

    @property
    def active(self) -> bool:
        return bool(self.config.enabled and self.config.bot_token and self.config.chat_id)

    def should_notify(self, event: str) -> bool:
        return self.active and (event in self.config.notify_on or "all" in self.config.notify_on)

    def send(self, text: str, event: str = "error") -> None:
        if not self.should_notify(event):
            return
        url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
        try:
            response = requests.post(
                url,
                json={"chat_id": self.config.chat_id, "text": text[:3900], "disable_web_page_preview": True},
                timeout=10,
            )
            if response.status_code >= 400:
                log.warning("Telegram odmietol spravu (%s): %s", response.status_code, response.text[:200])
        except requests.RequestException as exc:
            log.warning("Telegram sprava sa neodoslala: %s", exc)


def build_notifier(config: Optional[TelegramConfig]) -> Notifier:
    return Notifier(config or TelegramConfig())
