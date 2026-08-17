#!/usr/bin/env python3
"""Travian Farmbot - vstupny bod.

Priklady:
    python run.py                    # spusti bota podla planu v config.yaml
    python run.py --list             # vypise ulohy a ich plan
    python run.py --once "Farm listy"  # spusti jednu ulohu hned a skonci
    python run.py --browser          # otvori prehliadac na rucne prihlasenie
    python run.py --check            # overi konfiguraciu a skonci
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="travian-farmbot",
        description="Autonomny Travian bot s casovacom.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--config", default=str(BASE_DIR / "config.yaml"),
                        help="cesta ku konfiguracii (default: config.yaml)")
    parser.add_argument("--once", metavar="ULOHA",
                        help="spusti jednu ulohu podla nazvu a skonci")
    parser.add_argument("--list", action="store_true", help="vypise nakonfigurovane ulohy")
    parser.add_argument("--check", action="store_true", help="overi konfiguraciu a skonci")
    parser.add_argument("--browser", action="store_true",
                        help="otvori prehliadac a pocka - na rucne prihlasenie / cookies")
    parser.add_argument("--no-dashboard", action="store_true", help="nespusti webovy dashboard")
    parser.add_argument("--headless", action="store_true", help="vynuti bezokenny rezim")
    parser.add_argument("--show", action="store_true", help="vynuti viditelny prehliadac")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    load_dotenv(BASE_DIR / ".env")

    # Imports happen after load_dotenv so ${ENV} references in the config resolve.
    from travianbot.config import Config, ConfigError
    from travianbot.logging_setup import setup_logging

    try:
        config = Config.load(args.config)
    except ConfigError as exc:
        print(f"\n  Chyba v konfiguracii: {exc}\n", file=sys.stderr)
        return 2

    if args.headless:
        config.browser.headless = True
    if args.show:
        config.browser.headless = False
    if args.no_dashboard:
        config.dashboard.enabled = False

    log_path = setup_logging(config.logging, config.base_dir)
    log = logging.getLogger("travianbot")

    from travianbot.scheduler import BotRunner
    from travianbot.tasks import known_types

    try:
        runner = BotRunner(config)
    except KeyError as exc:
        print(f"\n  {exc}\n  Dostupne typy uloh: {', '.join(known_types())}\n", file=sys.stderr)
        return 2

    if args.check or args.list:
        _print_tasks(config)
        print(f"\n  Konfiguracia je v poriadku. Log: {log_path}")
        print(f"  Server: {config.account.server_url}  ucet: {config.account.username}\n")
        return 0

    if args.browser:
        return _manual_browser(runner, log)

    if args.once:
        result = runner.run_single(args.once)
        log.info("Vysledok: %s", result.message)
        runner.shutdown()
        return 0 if result.ok else 1

    if config.dashboard.enabled:
        from travianbot.dashboard import start_dashboard
        start_dashboard(runner)

    log.info("Travian Farmbot - server %s, ucet %s", config.account.server_url, config.account.username)
    runner.run_forever()
    return 0


def _print_tasks(config) -> None:  # noqa: ANN001 - simple CLI helper
    print("\n  Nakonfigurovane ulohy:\n")
    print(f"  {'stav':6} {'nazov':26} {'typ':12} plan")
    print("  " + "-" * 74)
    for task in config.tasks:
        state = "ON " if task.enabled else "off"
        night = "  [aj v noci]" if task.run_in_quiet_hours else ""
        print(f"  {state:6} {task.name[:25]:26} {task.type:12} {task.schedule.describe()}{night}")
    quiet = config.behavior.quiet_hours
    if quiet.enabled:
        print(f"\n  Nocny rezim: {quiet.start:%H:%M} - {quiet.end:%H:%M} (ulohy sa preskakuju)")


def _manual_browser(runner, log) -> int:  # noqa: ANN001
    """Open the browser and wait, so the user can log in / accept banners once.
    The persistent profile keeps the session for later automated runs."""
    from travianbot.selectors import PATHS

    runner.session.config.browser.headless = False
    runner.session.start()
    runner.session.goto(PATHS["dorf1"][0])
    print("\n  Prehliadac je otvoreny. Prihlas sa (a odklikaj pripadne okna hry).")
    print("  Session sa ulozi do profilu, takze bot sa uz prihlasovat nebude musiet.")
    try:
        input("  Az budes hotovy, stlac Enter...")
    except (EOFError, KeyboardInterrupt):
        pass
    logged_in = runner.session.is_logged_in()
    log.info("Stav prihlasenia: %s", "prihlaseny" if logged_in else "NEPRIHLASENY")
    runner.shutdown()
    return 0 if logged_in else 1


if __name__ == "__main__":
    sys.exit(main())
