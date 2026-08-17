"""Task base class, result type and the task registry."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type

from ..browser import TravianSession
from ..config import TaskConfig

log = logging.getLogger(__name__)


@dataclass
class TaskResult:
    ok: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def success(message: str, **details: Any) -> "TaskResult":
        return TaskResult(True, message, details)

    @staticmethod
    def skipped(message: str, **details: Any) -> "TaskResult":
        return TaskResult(True, message, dict(details, skipped=True))

    @staticmethod
    def failure(message: str, **details: Any) -> "TaskResult":
        return TaskResult(False, message, details)


class Task:
    """Base class. Subclasses implement `execute` and set `type_name`."""

    type_name: str = ""

    def __init__(self, config: TaskConfig):
        self.config = config
        self.options = config.options

    @property
    def name(self) -> str:
        return self.config.name

    def opt(self, key: str, default: Any = None) -> Any:
        return self.options.get(key, default)

    def execute(self, session: TravianSession) -> TaskResult:  # pragma: no cover - interface
        raise NotImplementedError

    def run(self, session: TravianSession) -> TaskResult:
        session.ensure_logged_in()
        return self.execute(session)


# ---------------------------------------------------------------------- #
# registry
# ---------------------------------------------------------------------- #
_REGISTRY: Dict[str, Type[Task]] = {}


def register(cls: Type[Task]) -> Type[Task]:
    if not cls.type_name:
        raise ValueError(f"{cls.__name__} nema nastaveny type_name.")
    _REGISTRY[cls.type_name] = cls
    return cls


def create_task(config: TaskConfig) -> Task:
    cls = _REGISTRY.get(config.type)
    if cls is None:
        known = ", ".join(sorted(_REGISTRY)) or "-"
        raise KeyError(f"Neznamy typ ulohy {config.type!r}. Dostupne typy: {known}")
    return cls(config)


def known_types() -> List[str]:
    return sorted(_REGISTRY)


# ---------------------------------------------------------------------- #
# shared helpers
# ---------------------------------------------------------------------- #
@dataclass
class Village:
    name: str
    did: Optional[str]
    index: int


def list_villages(session: TravianSession) -> List[Village]:
    """Read the village switcher in the sidebar."""
    from ..selectors import PATHS

    if not session.has("village_list_entry", timeout_ms=2000):
        session.goto(PATHS["dorf1"][0])
    villages: List[Village] = []
    for index, entry in enumerate(session.find_all("village_list_entry"), start=1):
        try:
            text = (entry.inner_text(timeout=2000) or "").strip().splitlines()
            name = next((line.strip() for line in text if line.strip()), f"Dedina {index}")
            href = entry.locator("a").first.get_attribute("href", timeout=2000) or ""
        except Exception:  # noqa: BLE001 - sidebar markup varies a lot
            continue
        match = re.search(r"newdid=(\d+)", href)
        villages.append(Village(name=name, did=match.group(1) if match else None, index=index))
    return villages


def switch_village(session: TravianSession, wanted: Any) -> Optional[Village]:
    """Switch to a village by name (str) or 1-based sidebar position (int).

    Returns the village that is now active, or None when `wanted` is empty
    (meaning: stay in the currently selected village).
    """
    if wanted in (None, "", "current"):
        return None

    villages = list_villages(session)
    if not villages:
        return None

    target: Optional[Village] = None
    if isinstance(wanted, int) or (isinstance(wanted, str) and wanted.isdigit()):
        position = int(wanted)
        target = next((v for v in villages if v.index == position), None)
    else:
        needle = str(wanted).strip().lower()
        target = next((v for v in villages if v.name.strip().lower() == needle), None)
        if target is None:
            target = next((v for v in villages if needle in v.name.strip().lower()), None)

    if target is None:
        available = ", ".join(v.name for v in villages)
        raise ValueError(f"Dedina {wanted!r} sa nenasla. Dostupne: {available}")

    if target.did:
        session.goto(f"/dorf1.php?newdid={target.did}")
    return target


def parse_int(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    match = re.search(r"-?\d+", text.replace(" ", "").replace("\xa0", "").replace(" ", ""))
    return int(match.group(0)) if match else None


TaskFactory = Callable[[TaskConfig], Task]
