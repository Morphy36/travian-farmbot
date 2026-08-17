"""Loading and validation of config.yaml."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import time as dtime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .utils import parse_duration, parse_hhmm

_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(Exception):
    """Raised when config.yaml is missing something or has a bad value."""


def _expand_env(value: Any) -> Any:
    """Recursively replace ${VAR} references with environment variables."""
    if isinstance(value, str):
        def repl(match: "re.Match[str]") -> str:
            name = match.group(1)
            resolved = os.environ.get(name)
            if resolved is None:
                raise ConfigError(
                    f"V configu je odkaz na premennu prostredia ${{{name}}}, ale tá nie je nastavená "
                    f"(pridaj ju do súboru .env)."
                )
            return resolved
        return _ENV_RE.sub(repl, value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


@dataclass
class AccountConfig:
    server_url: str
    username: str
    password: str

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AccountConfig":
        server_url = str(data.get("server_url", "")).strip().rstrip("/")
        username = str(data.get("username", "")).strip()
        password = str(data.get("password", ""))
        if not server_url:
            raise ConfigError("account.server_url je povinny (napr. https://ts1.x1.europe.travian.com).")
        if not server_url.startswith(("http://", "https://")):
            raise ConfigError("account.server_url musi zacinat http:// alebo https://.")
        if not username:
            raise ConfigError("account.username je povinny.")
        if not password:
            password = os.environ.get("TRAVIAN_PASSWORD", "")
        if not password:
            raise ConfigError(
                "Heslo nie je nastavene. Vypln account.password v config.yaml alebo "
                "TRAVIAN_PASSWORD v subore .env."
            )
        return AccountConfig(server_url=server_url, username=username, password=password)


@dataclass
class BrowserConfig:
    headless: bool = False
    profile_dir: str = "data/profile"
    slow_mo_ms: int = 0
    locale: str = "sk-SK"
    user_agent: Optional[str] = None
    viewport_width: int = 1440
    viewport_height: int = 900
    timeout_ms: int = 30000
    close_when_idle_minutes: float = 0.0  # 0 = nechaj prehliadac otvoreny

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "BrowserConfig":
        viewport = data.get("viewport") or {}
        return BrowserConfig(
            headless=bool(data.get("headless", False)),
            profile_dir=str(data.get("profile_dir", "data/profile")),
            slow_mo_ms=int(data.get("slow_mo_ms", 0)),
            locale=str(data.get("locale", "sk-SK")),
            user_agent=data.get("user_agent") or None,
            viewport_width=int(viewport.get("width", 1440)),
            viewport_height=int(viewport.get("height", 900)),
            timeout_ms=int(data.get("timeout_ms", 30000)),
            close_when_idle_minutes=float(data.get("close_when_idle_minutes", 0) or 0),
        )


@dataclass
class QuietHours:
    enabled: bool = False
    start: dtime = dtime(23, 30)
    end: dtime = dtime(6, 30)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "QuietHours":
        data = data or {}
        return QuietHours(
            enabled=bool(data.get("enabled", False)),
            start=parse_hhmm(data.get("from", "23:30")),
            end=parse_hhmm(data.get("to", "06:30")),
        )


@dataclass
class BehaviorConfig:
    action_delay: Tuple[float, float] = (0.6, 2.2)
    default_jitter_pct: float = 20.0
    quiet_hours: QuietHours = field(default_factory=QuietHours)
    max_consecutive_failures: int = 5
    screenshot_on_error: bool = True

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "BehaviorConfig":
        data = data or {}
        delay = data.get("action_delay", [0.6, 2.2])
        if not isinstance(delay, (list, tuple)) or len(delay) != 2:
            raise ConfigError("behavior.action_delay musi byt zoznam dvoch cisel, napr. [0.6, 2.2].")
        return BehaviorConfig(
            action_delay=(float(delay[0]), float(delay[1])),
            default_jitter_pct=float(data.get("default_jitter_pct", 20)),
            quiet_hours=QuietHours.from_dict(data.get("quiet_hours") or {}),
            max_consecutive_failures=int(data.get("max_consecutive_failures", 5)),
            screenshot_on_error=bool(data.get("screenshot_on_error", True)),
        )


@dataclass
class DashboardConfig:
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8777

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "DashboardConfig":
        data = data or {}
        return DashboardConfig(
            enabled=bool(data.get("enabled", True)),
            host=str(data.get("host", "127.0.0.1")),
            port=int(data.get("port", 8777)),
        )


@dataclass
class TelegramConfig:
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""
    notify_on: List[str] = field(default_factory=lambda: ["error"])

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "TelegramConfig":
        data = data or {}
        return TelegramConfig(
            enabled=bool(data.get("enabled", False)),
            bot_token=str(data.get("bot_token", "")),
            chat_id=str(data.get("chat_id", "")),
            notify_on=[str(x).lower() for x in (data.get("notify_on") or ["error"])],
        )


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "logs/bot.log"
    max_bytes: int = 2_000_000
    backup_count: int = 5

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "LoggingConfig":
        data = data or {}
        return LoggingConfig(
            level=str(data.get("level", "INFO")).upper(),
            file=str(data.get("file", "logs/bot.log")),
            max_bytes=int(data.get("max_bytes", 2_000_000)),
            backup_count=int(data.get("backup_count", 5)),
        )


@dataclass
class ScheduleConfig:
    """One of: every (interval), cron (cron expression), at (list of daily times)."""

    every_seconds: Optional[float] = None
    jitter_seconds: float = 0.0
    cron: Optional[str] = None
    at_times: List[dtime] = field(default_factory=list)
    start_delay_seconds: float = 0.0

    @staticmethod
    def from_dict(data: Dict[str, Any], default_jitter_pct: float) -> "ScheduleConfig":
        data = data or {}
        every = data.get("every")
        cron = data.get("cron")
        at = data.get("at")
        given = [x for x in (every, cron, at) if x]
        if len(given) == 0:
            raise ConfigError("schedule musi obsahovat 'every', 'cron' alebo 'at'.")
        if len(given) > 1:
            raise ConfigError("schedule moze obsahovat len jednu z moznosti: 'every', 'cron', 'at'.")

        every_seconds = parse_duration(every) if every else None
        if "jitter" in data:
            jitter_seconds = parse_duration(data.get("jitter"))
        elif every_seconds:
            jitter_seconds = every_seconds * default_jitter_pct / 100.0
        else:
            jitter_seconds = 0.0

        at_times: List[dtime] = []
        if at:
            if isinstance(at, str):
                at = [at]
            at_times = [parse_hhmm(x) for x in at]

        return ScheduleConfig(
            every_seconds=every_seconds,
            jitter_seconds=jitter_seconds,
            cron=str(cron) if cron else None,
            at_times=at_times,
            start_delay_seconds=parse_duration(data.get("start_delay"), 0),
        )

    def describe(self) -> str:
        if self.every_seconds:
            from .utils import format_duration
            base = f"kazdych {format_duration(self.every_seconds)}"
            if self.jitter_seconds:
                base += f" (±{format_duration(self.jitter_seconds)})"
            return base
        if self.cron:
            return f"cron: {self.cron}"
        if self.at_times:
            return "denne o " + ", ".join(t.strftime("%H:%M") for t in self.at_times)
        return "-"


@dataclass
class TaskConfig:
    name: str
    type: str
    enabled: bool
    schedule: ScheduleConfig
    options: Dict[str, Any]
    run_in_quiet_hours: bool = False

    @staticmethod
    def from_dict(data: Dict[str, Any], index: int, default_jitter_pct: float) -> "TaskConfig":
        if not isinstance(data, dict):
            raise ConfigError(f"tasks[{index}] musi byt objekt.")
        task_type = str(data.get("type", "")).strip()
        if not task_type:
            raise ConfigError(f"tasks[{index}] nema vyplneny 'type'.")
        name = str(data.get("name") or task_type)
        return TaskConfig(
            name=name,
            type=task_type,
            enabled=bool(data.get("enabled", True)),
            schedule=ScheduleConfig.from_dict(data.get("schedule") or {}, default_jitter_pct),
            options=dict(data.get("options") or {}),
            run_in_quiet_hours=bool(data.get("run_in_quiet_hours", False)),
        )


@dataclass
class Config:
    account: AccountConfig
    browser: BrowserConfig
    behavior: BehaviorConfig
    dashboard: DashboardConfig
    telegram: TelegramConfig
    logging: LoggingConfig
    tasks: List[TaskConfig]
    selectors: Dict[str, List[str]]
    base_dir: Path

    @staticmethod
    def load(path: str | Path) -> "Config":
        path = Path(path)
        if not path.exists():
            raise ConfigError(
                f"Konfiguracny subor {path} neexistuje. Skopiruj config.example.yaml na config.yaml "
                f"a vypln prihlasovacie udaje."
            )
        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        if not isinstance(raw, dict):
            raise ConfigError("config.yaml musi obsahovat objekt na najvyssej urovni.")
        raw = _expand_env(raw)

        behavior = BehaviorConfig.from_dict(raw.get("behavior") or {})
        tasks_raw = raw.get("tasks") or []
        if not isinstance(tasks_raw, list):
            raise ConfigError("tasks musi byt zoznam.")
        tasks = [
            TaskConfig.from_dict(item, i, behavior.default_jitter_pct)
            for i, item in enumerate(tasks_raw)
        ]
        seen: Dict[str, int] = {}
        for task in tasks:
            if task.name in seen:
                raise ConfigError(f"Dve ulohy maju rovnaky nazov: {task.name!r}. Nazvy musia byt unikatne.")
            seen[task.name] = 1

        selectors_raw = raw.get("selectors") or {}
        selectors: Dict[str, List[str]] = {}
        for key, value in selectors_raw.items():
            selectors[str(key)] = [value] if isinstance(value, str) else [str(v) for v in value]

        return Config(
            account=AccountConfig.from_dict(raw.get("account") or {}),
            browser=BrowserConfig.from_dict(raw.get("browser") or {}),
            behavior=behavior,
            dashboard=DashboardConfig.from_dict(raw.get("dashboard") or {}),
            telegram=TelegramConfig.from_dict((raw.get("notifications") or {}).get("telegram") or {}),
            logging=LoggingConfig.from_dict(raw.get("logging") or {}),
            tasks=tasks,
            selectors=selectors,
            base_dir=path.resolve().parent,
        )

    def resolve(self, relative: str) -> Path:
        """Resolve a config-relative path against the config file's directory."""
        candidate = Path(relative)
        return candidate if candidate.is_absolute() else (self.base_dir / candidate)
