# Travian Farmbot

Autonómny bot pre Travian s vlastným **časovačom** — povieš mu, čo a kedy má robiť,
a on to robí sám. Beží na Windows, inštalácia je na dva kliky, priebeh vidíš
v jednoduchom webovom dashboarde.

```
┌─ config.yaml ─────────┐     ┌─ plánovač ──────┐     ┌─ prehliadač ────┐
│ Farm listy: každých   │ ──> │ fronta úloh     │ ──> │ Chromium        │
│   22m (±7m)           │     │ (jedna po       │     │ (Playwright)    │
│ Hrdina: každých 40m   │     │  druhej)        │     │ prihlásený,     │
│ Stavanie: cron        │     │ nočný režim     │     │ profil sa drží  │
└───────────────────────┘     └─────────────────┘     └─────────────────┘
                                      │
                              http://127.0.0.1:8777  ← dashboard
```

> [!WARNING]
> **Botovanie porušuje podmienky používania Travianu** a hrozí zaň zablokovanie
> účtu. Projekt je určený na štúdium automatizácie prehliadača a používaš ho
> na vlastné riziko a zodpovednosť.

---

## Čo bot vie

| Typ úlohy | Čo robí |
|---|---|
| `farmlist` | Odošle farm listy zo zhromaždiska — všetky naraz alebo len vybrané podľa názvu |
| `adventure` | Pošle hrdinu na dobrodružstvo, ak má dosť zdravia |
| `build` | Vylepší budovu/políčko z fronty (prvé, na ktoré sú suroviny) |
| `train` | Natrénuje jednotky v kasárňach / stajni / dielni |
| `keepalive` | Načíta pár stránok, aby session nevypadla a aktivita nevyzerala strojovo |
| `screenshot` | Ladiaca úloha — uloží screenshot + HTML stránky do `data/debug` |

Ďalšie vlastnosti:

- **Časovač** — interval (`every: 20m`), presný čas (`at: ["07:15","19:40"]`) alebo cron (`cron: "*/30 6-23 * * *"`)
- **Náhodný rozptyl** (jitter) na každom intervale + náhodné pauzy medzi klikmi
- **Nočný režim** — v zadanom okne sa úlohy preskakujú (okrem tých, ktoré to majú povolené)
- **Dashboard** na `127.0.0.1:8777` — stav, ďalší beh, posledný výsledok, log, ručné spustenie, pauza
- **Automatická pauza** po N chybách za sebou + voliteľné **Telegram** upozornenia
- **Selektory v configu** — keď hra zmení vzhľad, prepíšeš selektor v `config.yaml`, nie kód

---

## Inštalácia na Windows — celý postup od nuly

### 1. Nainštaluj Python

**Stiahni:** [python-3.12.10-amd64.exe](https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe)
(64-bit Windows inštalátor; iné verzie na [python.org/downloads/windows](https://www.python.org/downloads/windows/))

V prvom okne inštalátora **zaškrtni dole „Add python.exe to PATH"** a potom
*Install Now*. Bez tejto fajky `install.bat` Python nenájde.

Overenie — otvor `cmd` (Win + R → `cmd`) a napíš `python --version`.
Musí vypísať číslo verzie, nie chybu.

### 2. Stiahni bota

**Stiahni ZIP:** [travian-farmbot-main.zip](https://github.com/Morphy36/travian-farmbot/archive/refs/heads/main.zip)

Rozbaľ ho (pravý klik → *Extrahovať všetko*) do jednoduchej cesty, napr. **`C:\travian-farmbot`**.

V priečinku musia byť priamo `install.bat`, `run.py`, `config.example.yaml` —
ZIP z GitHubu vytvára obal `travian-farmbot-main`, takže rozbaľ jeho **obsah**.

> Nedávaj bota do `Program Files` (potrebuje práva na zápis) ani do priečinka
> synchronizovaného OneDrive-om (bije sa to s profilom prehliadača).

### 3. Spusti install.bat

Dvojklik na **`install.bat`**. Vytvorí virtuálne prostredie, doinštaluje knižnice,
stiahne Chromium (~130 MB) a pripraví `config.yaml`. Trvá to pár minút.

Ak vyskočí modré okno *„Windows chránil váš počítač"* → **Ďalšie informácie →
Spustiť tak či tak**. To je bežné pri každom `.bat` stiahnutom z internetu.

### 4. Vyplň config.yaml

Inštalátor sa na konci spýta, či ho otvoriť. Vyplň aspoň:

```yaml
account:
  server_url: "https://tsX.xN.europe.travian.com"   # adresa TVOJHO servera
  username: "tvoje-meno"
  password: "tvoje-heslo"
```

`server_url` je to, čo máš v adresnom riadku počas hrania, bez `/dorf1.php` na
konci — nie `travian.com`. Zvyšok (časovač) môžeš nechať tak, funguje hneď.

### 5. Prihlás sa raz ručne

Dvojklik na **`login.bat`** → otvorí sa prehliadač → prihlás sa do hry a odklikaj
prípadné cookie okná a dialógy hry → vráť sa do čierneho okna a stlač Enter.

Stačí raz. Session sa uloží do `data\profile`, bot sa už prihlasovať nemusí.

### 6. Skúška a spustenie

Najprv **`test.bat`** → vypíše úlohy → napíš `Farm listy` a Enter. Spustí len tú
jednu úlohu, takže hneď vidíš, či bot na tvojom serveri farm listy nájde.

Potom **`start.bat`** — čierne okno nechaj otvorené, pokiaľ beží, beží bot
(ukončenie `Ctrl+C`). Dashboard: **<http://127.0.0.1:8777>**

| Súbor | Na čo je |
|---|---|
| `install.bat` | jednorazová inštalácia |
| `start.bat` | spustenie bota podľa časovača |
| `login.bat` | otvorí prehliadač na ručné prihlásenie |
| `test.bat` | vypíše úlohy a spustí jednu na skúšku |

---

## Nastavenie časovača

Celý plán je v `config.yaml` v sekcii `tasks`. Každá úloha vyzerá takto:

```yaml
tasks:
  - name: "Farm listy"        # ľubovoľný unikátny názov
    type: farmlist            # typ úlohy z tabuľky vyššie
    enabled: true
    schedule:
      every: "22m"            # každých 22 minút…
      jitter: "7m"            # …±7 minút náhodne
    options:
      run_on_start: true      # spusti hneď po štarte bota
      lists: ["all"]          # alebo ["Sever", "Juh"] podľa názvov v hre
```

**Tri spôsoby plánovania** (v jednej úlohe vždy práve jeden):

```yaml
schedule: {every: "20m", jitter: "5m"}     # opakovane
schedule: {at: ["07:15", "12:00", "19:40"]}  # každý deň o presnom čase
schedule: {cron: "*/30 6-23 * * *"}        # cron: min hod deň mesiac deň-v-týždni
```

Voliteľne `start_delay: "2m"` (prvý beh až o 2 minúty po štarte) a
`run_in_quiet_hours: true` (úloha beží aj v nočnom režime).

**Nočný režim** sa nastavuje raz pre celého bota:

```yaml
behavior:
  quiet_hours:
    enabled: true
    from: "23:40"
    to: "06:20"
```

### Príklady úloh

```yaml
  # Raiduj len dva konkrétne farm listy, každú polhodinu
  - name: "Farmenie sever"
    type: farmlist
    schedule: {every: "30m", jitter: "8m"}
    options:
      village: "Hlavná dedina"
      lists: ["Sever", "Blizke dediny"]

  # Stavaj, keď sú suroviny — skúša sa zhora nadol, postaví sa prvé možné
  - name: "Stavanie"
    type: build
    schedule: {every: "15m"}
    options:
      upgrades_per_run: 1
      queue:
        - {slot: 1}
        - {slot: 5}
        - {slot: 26, max_level: 20}

  # Trénuj vojakov každé tri hodiny
  - name: "Trening"
    type: train
    schedule: {cron: "0 */3 * * *"}
    options:
      slot: 19          # číslo políčka s kasárňami
      gid: 19           # 19 kasárne, 20 stajňa, 21 dielňa
      units: {t1: max}
```

---

## Príkazový riadok

`start.bat` posiela argumenty ďalej do `run.py`, takže funguje aj:

```bash
start.bat --list                 # vypíše úlohy a ich plán
start.bat --once "Farm listy"    # spustí jednu úlohu a skončí
start.bat --headless             # bez viditeľného okna prehliadača
start.bat --no-dashboard         # bez webového dashboardu
start.bat --check                # len overí konfiguráciu
```

---

## Keď bot prestane niečo nachádzať

Travian občas zmení HTML a bot napíše napr. *„Nenašiel som stránku s farm listami"*.
Vtedy:

1. Zapni ladiacu úlohu `screenshot` (alebo nechaj `screenshot_on_error: true`) —
   do `data/debug` sa uloží obrázok aj HTML stránky.
2. V HTML nájdi správnu triedu tlačidla.
3. Dopíš ju do `config.yaml`, kód sa meniť nemusí:

```yaml
selectors:
  farmlist_start_all:
    - "button.nova-trieda-tlacidla"
```

Zoznam všetkých kľúčov je v [`travianbot/selectors.py`](travianbot/selectors.py).
Tvoje hodnoty sa skúšajú ako prvé, pôvodné zostávajú ako záloha.

---

## Automatické spúšťanie po štarte Windows

Win + R → `shell:startup` → do priečinka daj zástupcu na `start.bat`.
Alebo cez Plánovač úloh (Task Scheduler): *Vytvoriť úlohu → Spúšťač: Pri prihlásení
→ Akcia: spustiť `start.bat`*, v poli „Začať v" nastav priečinok bota.

---

## Štruktúra projektu

```
travian-farmbot/
├── run.py                  vstupný bod / CLI
├── config.example.yaml     vzor konfigurácie (skopíruje sa na config.yaml)
├── install.bat start.bat login.bat test.bat
└── travianbot/
    ├── config.py           načítanie a validácia configu
    ├── browser.py          Playwright session, prihlásenie, hľadanie prvkov
    ├── selectors.py        všetky CSS selektory a URL na jednom mieste
    ├── scheduler.py        plánovač + fronta + vykonávanie úloh
    ├── state.py            stav pre dashboard
    ├── dashboard.py        webový dashboard (Flask)
    ├── notify.py           Telegram upozornenia
    └── tasks/              jednotlivé typy úloh
```

Nový typ úlohy = jeden súbor v `travianbot/tasks/` s triedou označenou
`@register`, `type_name = "nieco"` a metódou `execute(session)`.

---

## Bezpečnosť

- `config.yaml` a `.env` sú v `.gitignore` — heslo sa nikdy nedostane do gitu.
- Dashboard počúva len na `127.0.0.1` a **nemá heslo** — nevystavuj ho do siete.
- Profil prehliadača v `data/profile` obsahuje prihlasovacie cookies — je to
  rovnako citlivé ako heslo.

## Licencia

MIT — pozri [LICENSE](LICENSE).
