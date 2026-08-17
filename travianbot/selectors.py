"""Central place for every CSS/text selector and URL path the bot uses.

Travian changes its markup between versions and servers, so each entry is a
*list of candidates* that is tried in order. If the bot stops finding something
after a game update you can override any key in config.yaml under `selectors:`
without touching the code, e.g.

    selectors:
      farmlist_start_all:
        - "button.newStartAll"
"""

from __future__ import annotations

from typing import Dict, List

# --- URL paths (relative to the server URL) -------------------------------
PATHS: Dict[str, List[str]] = {
    # Resource overview / village centre - also used as "is the session alive?" probe.
    "dorf1": ["/dorf1.php"],
    "dorf2": ["/dorf2.php"],
    "login": ["/login.php", "/"],
    # Rally point -> farm lists. Different versions use different entry points.
    "farmlist": [
        "/build.php?id=39&gid=16&tt=99",
        "/build.php?gid=16&tt=99",
        "/build.php?tt=99",
    ],
    "hero_adventures": ["/hero/adventures", "/hero.php?t=3"],
    "hero_attributes": ["/hero/attributes", "/hero.php?t=1"],
    "build_slot": ["/build.php?id={slot}"],
    "build_slot_gid": ["/build.php?id={slot}&gid={gid}"],
}

DEFAULT_SELECTORS: Dict[str, List[str]] = {
    # --- login ---------------------------------------------------------
    "login_username": [
        'input[name="name"]',
        'input[name="user"]',
        'input[name="username"]',
        '#name',
    ],
    "login_password": [
        'input[name="password"]',
        'input[type="password"]',
        '#password',
    ],
    "login_submit": [
        'button[type="submit"]',
        'input[type="submit"]',
        'button:has-text("Login")',
        'button:has-text("Prihlásiť")',
    ],
    # Anything of these on the page means we are inside the game.
    "logged_in_marker": [
        "#resourceFieldContainer",
        "#villageContent",
        "#stockBar",
        "#navigation",
        ".villageList",
    ],

    # --- farm lists ----------------------------------------------------
    "farmlist_page_marker": [
        ".raidList",
        "#raidList",
        ".farmListHeader",
        '[class*="farmList"]',
    ],
    "farmlist_start_all": [
        "button.startAllFarmLists",
        "button.startFarmListsAll",
        ".startAllRaids button",
        'button:has-text("Start all")',
        'button:has-text("Spustiť všetky")',
        'button:has-text("Alle starten")',
    ],
    "farmlist_container": [
        ".raidList",
        '[class*="farmListHeader"]',
    ],
    "farmlist_start_one": [
        "button.startFarmList",
        "button.startRaid",
        ".startFarmList",
        'button:has-text("Start raid")',
    ],
    "farmlist_name": [
        ".listName",
        ".farmListName",
        ".name",
    ],

    # --- hero / adventures ---------------------------------------------
    "hero_health_text": [
        ".heroHealthBar .value",
        "#attributes .health .value",
        ".health .value",
        ".heroHealth",
    ],
    "adventure_row": [
        "#adventureListForm tbody tr",
        ".adventureList tbody tr",
        'table.adventures tbody tr',
    ],
    "adventure_start": [
        "button.gotoAdventure",
        "a.gotoAdventure",
        'button:has-text("Start adventure")',
        'button:has-text("Vyraziť")',
        "td.goTo button",
    ],
    "adventure_confirm": [
        "button.startAdventure",
        'button:has-text("Send hero")',
        'button:has-text("Start adventure")',
        "#start",
    ],
    "adventure_none_marker": [
        'text="No adventures"',
        ".noAdventures",
    ],

    # --- building -------------------------------------------------------
    "build_upgrade_button": [
        ".upgradeButtonsContainer .section1 button.build",
        "button.textButtonV1.green.build",
        ".upgradeBuilding button",
        'button:has-text("Upgrade to level")',
        'button:has-text("Vylepšiť na úroveň")',
    ],
    "build_level_text": [
        ".titleInHeader .level",
        "h1 .level",
        ".buildingLevel",
    ],
    "build_not_enough_marker": [
        ".contractLink .errorMessage",
        ".upgradeBlocked",
        ".notEnoughRes",
    ],

    # --- troop training --------------------------------------------------
    "train_max_link": [
        "a.maxValue",
        ".cta a",
        'a:has-text("max")',
    ],
    "train_submit": [
        "button.startTraining",
        'button:has-text("Train")',
        'button:has-text("Trénovať")',
        'button[value="ok"]',
    ],

    # --- villages ---------------------------------------------------------
    "village_list_entry": [
        ".villageList .listEntry",
        "#sidebarBoxVillagelist .listEntry",
        "#sidebarBoxVillagelist li",
    ],

    # --- session / errors --------------------------------------------------
    "session_expired_marker": [
        'text="Session expired"',
        ".error500",
        "#loginForm",
    ],
}


def build_selectors(overrides: Dict[str, List[str]] | None = None) -> Dict[str, List[str]]:
    """Merge user overrides on top of the defaults (overrides come first)."""
    merged = {key: list(value) for key, value in DEFAULT_SELECTORS.items()}
    for key, value in (overrides or {}).items():
        existing = merged.get(key, [])
        merged[key] = list(value) + [item for item in existing if item not in value]
    return merged
