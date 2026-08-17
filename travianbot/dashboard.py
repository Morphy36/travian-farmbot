"""Tiny local web dashboard: see the timer, the last results and the log,
and start / pause tasks by hand. Bound to localhost only."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from flask import Flask, jsonify, render_template_string, request

if TYPE_CHECKING:  # pragma: no cover
    from .scheduler import BotRunner

log = logging.getLogger(__name__)

PAGE = """<!doctype html>
<html lang="sk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Travian Farmbot</title>
<style>
  :root {
    --bg:#f6f7f9; --panel:#ffffff; --text:#1c1f24; --muted:#6b7280;
    --line:#e3e6ea; --ok:#15803d; --bad:#b91c1c; --accent:#2563eb;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#14171c; --panel:#1c2027; --text:#e7eaee; --muted:#98a1ad;
            --line:#2b313a; --ok:#4ade80; --bad:#f87171; --accent:#60a5fa; }
  }
  * { box-sizing:border-box; }
  body { margin:0; padding:24px; background:var(--bg); color:var(--text);
         font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif; }
  h1 { font-size:20px; margin:0 0 4px; }
  .sub { color:var(--muted); font-size:13px; margin-bottom:20px; }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:10px;
           padding:16px; margin-bottom:18px; }
  table { width:100%; border-collapse:collapse; }
  th, td { text-align:left; padding:8px 10px; border-bottom:1px solid var(--line); font-size:14px;
           vertical-align:top; }
  th { color:var(--muted); font-weight:600; font-size:12px; text-transform:uppercase;
       letter-spacing:.04em; }
  tr:last-child td { border-bottom:none; }
  .ok { color:var(--ok); } .bad { color:var(--bad); } .muted { color:var(--muted); }
  button { font:inherit; padding:5px 11px; border-radius:6px; border:1px solid var(--line);
           background:transparent; color:var(--text); cursor:pointer; }
  button:hover { border-color:var(--accent); color:var(--accent); }
  button.primary { background:var(--accent); border-color:var(--accent); color:#fff; }
  .badge { display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px;
           border:1px solid var(--line); }
  pre { margin:0; max-height:340px; overflow:auto; font-size:12.5px; line-height:1.45;
        background:var(--bg); padding:12px; border-radius:8px; }
  .row { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
  .grow { flex:1; }
  .wrap { overflow-x:auto; }
</style>
</head>
<body>
  <h1>Travian Farmbot</h1>
  <div class="sub" id="sub">načítavam…</div>

  <div class="panel">
    <div class="row">
      <span class="badge" id="status">—</span>
      <span class="muted" id="uptime"></span>
      <span class="grow"></span>
      <button class="primary" id="pauseBtn" onclick="togglePause()">Pozastaviť</button>
    </div>
  </div>

  <div class="panel wrap">
    <table>
      <thead><tr>
        <th>Úloha</th><th>Typ</th><th>Plán</th><th>Ďalší beh</th>
        <th>Posledný výsledok</th><th>Beh/Chyby</th><th></th>
      </tr></thead>
      <tbody id="tasks"></tbody>
    </table>
  </div>

  <div class="panel">
    <div class="row"><strong>Log</strong><span class="grow"></span>
      <span class="muted" id="logInfo"></span></div>
    <pre id="log"></pre>
  </div>

<script>
const fmt = t => t ? new Date(t).toLocaleString('sk-SK') : '—';
const rel = t => {
  if (!t) return '';
  const diff = Math.round((new Date(t) - new Date()) / 1000);
  if (diff <= 0) return 'teraz';
  if (diff < 60) return `o ${diff}s`;
  if (diff < 3600) return `o ${Math.round(diff/60)}m`;
  return `o ${Math.floor(diff/3600)}h ${Math.round((diff%3600)/60)}m`;
};
let paused = false;

async function refresh() {
  const res = await fetch('api/status');
  const data = await res.json();
  paused = data.paused;
  document.getElementById('sub').textContent =
    `${data.tasks.length} úloh · server čas ${fmt(data.now)}`;
  const status = document.getElementById('status');
  status.textContent = paused ? ('POZASTAVENÝ' + (data.pause_reason ? ' — ' + data.pause_reason : '')) : 'BEŽÍ';
  status.className = 'badge ' + (paused ? 'bad' : 'ok');
  document.getElementById('pauseBtn').textContent = paused ? 'Spustiť' : 'Pozastaviť';
  document.getElementById('uptime').textContent = 'štart: ' + fmt(data.started_at);

  document.getElementById('tasks').innerHTML = data.tasks.map(t => `
    <tr>
      <td><strong>${esc(t.name)}</strong>${t.running ? ' <span class="badge">beží</span>' : ''}</td>
      <td class="muted">${esc(t.type)}</td>
      <td class="muted">${esc(t.schedule_text)}</td>
      <td>${t.enabled ? (fmt(t.next_run) + ' <span class="muted">' + rel(t.next_run) + '</span>') : '<span class="muted">vypnuté</span>'}</td>
      <td class="${t.last_ok === null ? 'muted' : (t.last_ok ? 'ok' : 'bad')}">
        ${t.last_run ? esc(t.last_message || '') + '<br><span class="muted">' + fmt(t.last_run) + '</span>' : '<span class="muted">zatiaľ nebežalo</span>'}
      </td>
      <td class="muted">${t.runs} / ${t.failures}</td>
      <td style="white-space:nowrap">
        <button onclick="runNow('${esc(t.name)}')">Spustiť</button>
        <button onclick="toggle('${esc(t.name)}')">${t.enabled ? 'Vypnúť' : 'Zapnúť'}</button>
      </td>
    </tr>`).join('');
}

async function refreshLog() {
  const res = await fetch('api/log');
  const data = await res.json();
  const el = document.getElementById('log');
  el.textContent = data.lines.join('\\n');
  el.scrollTop = el.scrollHeight;
  document.getElementById('logInfo').textContent = data.file || '';
}

function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
async function post(url) { await fetch(url, {method:'POST'}); refresh(); }
const runNow = n => post('api/task/' + encodeURIComponent(n) + '/run');
const toggle = n => post('api/task/' + encodeURIComponent(n) + '/toggle');
const togglePause = () => post('api/pause/' + (paused ? 'off' : 'on'));

refresh(); refreshLog();
setInterval(refresh, 4000);
setInterval(refreshLog, 8000);
</script>
</body>
</html>
"""


def create_app(runner: "BotRunner") -> Flask:
    app = Flask(__name__)
    log_file: Path = runner.config.resolve(runner.config.logging.file)

    @app.get("/")
    def index() -> str:
        return render_template_string(PAGE)

    @app.get("/api/status")
    def status() -> Any:
        return jsonify(runner.state.snapshot())

    @app.post("/api/task/<name>/run")
    def run_task(name: str) -> Any:
        queued = runner.run_now(name)
        return jsonify({"queued": queued})

    @app.post("/api/task/<name>/toggle")
    def toggle_task(name: str) -> Any:
        enabled = not runner.state.is_enabled(name)
        runner.set_task_enabled(name, enabled)
        return jsonify({"enabled": enabled})

    @app.post("/api/pause/<mode>")
    def pause(mode: str) -> Any:
        runner.set_paused(mode == "on")
        return jsonify({"paused": runner.state.paused})

    @app.get("/api/log")
    def tail_log() -> Any:
        count = min(500, max(20, int(request.args.get("lines", 200))))
        lines: list[str] = []
        if log_file.exists():
            with log_file.open("r", encoding="utf-8", errors="replace") as handle:
                lines = handle.read().splitlines()[-count:]
        return jsonify({"file": str(log_file), "lines": lines})

    return app


def start_dashboard(runner: "BotRunner") -> None:
    """Run the dashboard in a daemon thread so it dies with the bot."""
    config = runner.config.dashboard
    if not config.enabled:
        return
    app = create_app(runner)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    def serve() -> None:
        try:
            app.run(host=config.host, port=config.port, threaded=True,
                    use_reloader=False, debug=False)
        except OSError as exc:
            log.warning("Dashboard sa nepodarilo spustit na porte %s: %s", config.port, exc)

    thread = threading.Thread(target=serve, name="dashboard", daemon=True)
    thread.start()
    log.info("Dashboard bezi na http://%s:%s", config.host, config.port)
