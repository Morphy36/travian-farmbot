"""The runner: turns config tasks into scheduled jobs and executes them one at
a time on a single browser session."""

from __future__ import annotations

import logging
import queue
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .browser import LoginFailed, TravianSession
from .config import Config, ScheduleConfig, TaskConfig
from .notify import build_notifier
from .state import BotState, TaskStatus
from .tasks import Task, TaskResult, create_task
from .utils import in_time_window

log = logging.getLogger(__name__)

# (task name, why it was queued, force = ignore pause/quiet hours)
QueueItem = Tuple[str, str, bool]


class BotRunner:
    def __init__(self, config: Config):
        self.config = config
        self.state = BotState()
        self.session = TravianSession(config)
        self.notifier = build_notifier(config.telegram)

        self.tasks: Dict[str, Task] = {}
        self._task_configs: Dict[str, TaskConfig] = {}
        self._queue: "queue.Queue[QueueItem]" = queue.Queue()
        self._queued_names: Set[str] = set()
        self._queue_lock = threading.Lock()
        self._scheduler = BackgroundScheduler()
        self._job_to_task: Dict[str, str] = {}
        self._stop_event = threading.Event()

        for task_config in config.tasks:
            task = create_task(task_config)
            self.tasks[task_config.name] = task
            self._task_configs[task_config.name] = task_config
            self.state.register_task(
                TaskStatus(
                    name=task_config.name,
                    type=task_config.type,
                    enabled=task_config.enabled,
                    schedule_text=task_config.schedule.describe(),
                )
            )

    # ------------------------------------------------------------------ #
    # scheduling
    # ------------------------------------------------------------------ #
    @staticmethod
    def _triggers(schedule: ScheduleConfig) -> List[BaseTrigger]:
        triggers: List[BaseTrigger] = []
        jitter = int(schedule.jitter_seconds) or None

        if schedule.every_seconds:
            start = datetime.now() + timedelta(seconds=schedule.start_delay_seconds or 0)
            triggers.append(
                IntervalTrigger(seconds=int(schedule.every_seconds), jitter=jitter, start_date=start)
            )
        elif schedule.cron:
            trigger = CronTrigger.from_crontab(schedule.cron)
            trigger.jitter = jitter
            triggers.append(trigger)
        else:
            for at_time in schedule.at_times:
                triggers.append(CronTrigger(hour=at_time.hour, minute=at_time.minute, jitter=jitter))
        return triggers

    def _build_jobs(self) -> None:
        for name, task_config in self._task_configs.items():
            for index, trigger in enumerate(self._triggers(task_config.schedule)):
                job_id = f"{name}#{index}"
                self._scheduler.add_job(
                    self._enqueue_from_schedule,
                    trigger=trigger,
                    id=job_id,
                    args=[name],
                    max_instances=1,
                    coalesce=True,
                    misfire_grace_time=300,
                    replace_existing=True,
                )
                self._job_to_task[job_id] = name
            log.info("Uloha %-24s -> %s", name, task_config.schedule.describe())

    def _enqueue_from_schedule(self, name: str) -> None:
        self.enqueue(name, reason="plan", force=False)

    def enqueue(self, name: str, reason: str = "plan", force: bool = False) -> bool:
        if name not in self.tasks:
            return False
        with self._queue_lock:
            if name in self._queued_names:
                log.debug("Uloha %s uz ceka vo fronte - preskakujem duplicitu.", name)
                return False
            self._queued_names.add(name)
        self._queue.put((name, reason, force))
        return True

    def _refresh_next_runs(self) -> None:
        next_by_task: Dict[str, datetime] = {}
        for job in self._scheduler.get_jobs():
            task_name = self._job_to_task.get(job.id)
            if not task_name or job.next_run_time is None:
                continue
            run_at = job.next_run_time.replace(tzinfo=None)
            current = next_by_task.get(task_name)
            if current is None or run_at < current:
                next_by_task[task_name] = run_at
        for name in self.tasks:
            self.state.update_task(name, next_run=next_by_task.get(name))

    # ------------------------------------------------------------------ #
    # execution
    # ------------------------------------------------------------------ #
    def _in_quiet_hours(self) -> bool:
        quiet = self.config.behavior.quiet_hours
        return quiet.enabled and in_time_window(datetime.now(), quiet.start, quiet.end)

    def _execute(self, item: QueueItem) -> None:
        name, reason, force = item
        with self._queue_lock:
            self._queued_names.discard(name)

        task = self.tasks.get(name)
        if task is None:
            return

        if not force:
            if self.state.paused:
                log.info("Bot je pozastaveny - '%s' preskocena.", name)
                return
            if not self.state.is_enabled(name):
                log.debug("Uloha '%s' je vypnuta - preskakujem.", name)
                return
            if self._in_quiet_hours() and not self._task_configs[name].run_in_quiet_hours:
                log.info("Nocny rezim - '%s' preskocena.", name)
                return

        log.info("--- Spustam ulohu '%s' (%s) ---", name, reason)
        self.state.update_task(name, running=True)
        started = datetime.now()
        try:
            result = task.run(self.session)
        except LoginFailed as exc:
            result = TaskResult.failure(str(exc))
        except Exception as exc:  # noqa: BLE001 - a broken task must not kill the bot
            log.exception("Uloha '%s' skoncila vynimkou.", name)
            if self.config.behavior.screenshot_on_error:
                self.session.dump(f"error-{name}")
            result = TaskResult.failure(f"{type(exc).__name__}: {exc}")
        finally:
            self.state.update_task(name, running=False)

        took = (datetime.now() - started).total_seconds()
        level = logging.INFO if result.ok else logging.WARNING
        log.log(level, "Uloha '%s' hotova za %.1fs: %s", name, took, result.message)
        self.state.record_run(name, result.ok, result.message)

        if result.ok:
            self.notifier.send(f"✅ {name}: {result.message}", event="success")
        else:
            self.notifier.send(f"⚠️ {name}: {result.message}", event="error")
            self._handle_failure()

    def _handle_failure(self) -> None:
        failures = self.state.consecutive_failures
        if failures == 2:
            log.warning("Dve chyby po sebe - restartujem prehliadac.")
            self.session.stop()
        limit = self.config.behavior.max_consecutive_failures
        if limit and failures >= limit:
            reason = f"{failures} chyb po sebe - bot pozastaveny, skontroluj log."
            log.error(reason)
            self.state.set_paused(True, reason)
            self.notifier.send(f"⛔ Bot pozastaveny: {reason}", event="error")

    # ------------------------------------------------------------------ #
    # public control (used by CLI and dashboard)
    # ------------------------------------------------------------------ #
    def run_now(self, name: str) -> bool:
        return self.enqueue(name, reason="rucne", force=True)

    def set_task_enabled(self, name: str, enabled: bool) -> None:
        self.state.set_enabled(name, enabled)
        log.info("Uloha '%s' %s.", name, "zapnuta" if enabled else "vypnuta")

    def set_paused(self, paused: bool) -> None:
        self.state.set_paused(paused, "rucne pozastavene" if paused else "")
        log.info("Bot %s.", "pozastaveny" if paused else "spusteny")

    def run_single(self, name: str) -> TaskResult:
        """Run one task synchronously (CLI `--once`), without the scheduler."""
        task = self.tasks.get(name)
        if task is None:
            available = ", ".join(self.tasks) or "-"
            raise KeyError(f"Uloha {name!r} neexistuje. Dostupne: {available}")
        try:
            return task.run(self.session)
        except Exception as exc:  # noqa: BLE001
            if self.config.behavior.screenshot_on_error:
                self.session.dump(f"error-{name}")
            return TaskResult.failure(f"{type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------ #
    def run_forever(self) -> None:
        self._build_jobs()
        self._scheduler.start()
        self._refresh_next_runs()

        for name, task_config in self._task_configs.items():
            if task_config.enabled and task_config.options.get("run_on_start"):
                self.enqueue(name, reason="start bota")

        log.info("Bot bezi. Ukoncenie: Ctrl+C.")
        try:
            while not self._stop_event.is_set():
                try:
                    item = self._queue.get(timeout=1.0)
                except queue.Empty:
                    self._refresh_next_runs()
                    continue
                self._execute(item)
                self._refresh_next_runs()
        except KeyboardInterrupt:
            log.info("Prijaty Ctrl+C - koncim.")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        self._stop_event.set()
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        self.session.stop()
        log.info("Bot zastaveny.")
