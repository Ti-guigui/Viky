"""Télécommande secrète : une page web à ouvrir sur votre téléphone (même Wi-Fi que le PC).

Elle permet de charger le secret (la carte choisie…), de déclencher une révélation,
de faire parler Viky, de passer les diapos ou de mettre l'écran au noir,
sans dire un mot. Protégée par un code PIN.
"""

from __future__ import annotations

import json
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<meta name="theme-color" content="#000"><title>Notes</title><style>
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;padding:14px;background:#000;color:#777;font:16px system-ui,sans-serif}
h2{font-size:13px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;margin:18px 0 8px;color:#555}
.row{display:flex;gap:8px;flex-wrap:wrap}
button{flex:1;min-width:64px;padding:16px 6px;border:1px solid #222;border-radius:12px;background:#111;
color:#bbb;font-size:17px}
button:active{background:#333}
button.on{border-color:#5b3fd1;color:#fff}
.red{color:#d33 !important}
input{width:100%;padding:14px;border-radius:12px;border:1px solid #222;background:#0b0b0b;color:#ddd;font-size:17px}
#status{font-size:14px;color:#555;min-height:20px}
#pin{max-width:160px}
</style></head><body>
<div id="login"><h2>Code</h2><input id="pin" type="password" inputmode="numeric" autocomplete="off">
<div class="row" style="margin-top:8px"><button onclick="savePin()">OK</button></div></div>
<div id="app" style="display:none">
<div id="status">…</div>
<h2>Mode</h2><div class="row">
<button id="stage" onclick="send('mode')">Spectacle</button>
<button onclick="send('noir')">Noir</button><button onclick="send('effacer')">Effacer</button></div>
<h2>Carte</h2><div class="row" id="ranks"></div>
<div class="row" style="margin-top:8px" id="suits"></div>
<h2>Secret (mot, nombre…)</h2><input id="secret" placeholder="ex. Paris">
<div class="row" style="margin-top:8px"><button onclick="send('secret', val('secret'))">Charger</button></div>
<h2>Effet</h2><div class="row">
<button onclick="send('reveler')">Révéler</button><button onclick="send('deviner')">Deviner</button></div>
<h2>Faire parler Viky</h2><input id="say" placeholder="Phrase à dire">
<div class="row" style="margin-top:8px"><button onclick="send('dire', val('say'))">Dire</button>
<button onclick="send('afficher', val('say'))">Afficher</button></div>
<h2>Diapos</h2><div class="row">
<button onclick="send('precedent')">◀</button><button onclick="send('suivant')">▶</button></div>
</div>
<script>
const ranks_ = document.getElementById('ranks'), suits_ = document.getElementById('suits');
const login = document.getElementById('login'), app = document.getElementById('app');
const statusEl = document.getElementById('status');
let pin = localStorage.getItem('pin') || '', rank = '';
const ranks = ['A','2','3','4','5','6','7','8','9','10','V','D','R'];
const suits = [['♥','red'],['♦','red'],['♣',''],['♠','']];
for (const r of ranks) { const b = document.createElement('button'); b.textContent = r;
  b.style.minWidth = '44px'; b.onclick = () => { rank = r; mark('#ranks button', b); }; ranks_.appendChild(b); }
for (const [s, c] of suits) { const b = document.createElement('button'); b.textContent = s; b.className = c;
  b.onclick = () => { if (rank) { send('secret', rank + s); mark('#suits button', b); } }; suits_.appendChild(b); }
function mark(sel, b) { document.querySelectorAll(sel).forEach(x => x.classList.remove('on')); b.classList.add('on'); }
function val(id) { const v = document.getElementById(id).value; document.getElementById(id).value = ''; return v; }
function savePin() { pin = document.getElementById('pin').value; localStorage.setItem('pin', pin); refresh(); }
async function call(action, value) {
  const r = await fetch('/api', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({pin, action, value: value || ''})});
  if (r.status === 403) { login.style.display = ''; app.style.display = 'none'; return null; }
  login.style.display = 'none'; app.style.display = ''; return r.json();
}
async function send(action, value) { const s = await call(action, value); if (s) show(s); }
async function refresh() { const s = await call('etat'); if (s) show(s); }
function show(s) { statusEl.textContent = (s.secret ? 'Secret : ' + s.secret : 'Aucun secret') + (s.message ? ' — ' + s.message : '');
  document.getElementById('stage').classList.toggle('on', s.spectacle); }
if (pin) refresh();
</script></body></html>"""


def local_ip() -> str:
    """Adresse du PC sur le réseau Wi-Fi local."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.1.1", 80))  # aucun paquet n'est envoyé
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def new_pin() -> str:
    return f"{secrets.randbelow(10000):04d}"


class Remote:
    def __init__(self, handle: Callable[[str, str], dict], pin: str, port: int = 8765) -> None:
        """`handle(action, valeur)` exécute l'action et renvoie l'état à afficher."""
        self.handle = handle
        self.pin = pin
        self.port = port
        self.server: ThreadingHTTPServer | None = None

    @property
    def url(self) -> str:
        return f"http://{local_ip()}:{self.port}"

    def start(self) -> None:
        remote = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:  # pas de bruit dans la console
                pass

            def _reply(self, code: int, body: bytes, kind: str) -> None:
                self.send_response(code)
                self.send_header("Content-Type", kind)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                if self.path in ("/", "/index.html"):
                    self._reply(200, PAGE.encode(), "text/html; charset=utf-8")
                else:
                    self._reply(404, b"", "text/plain")

            def do_POST(self) -> None:
                if self.path != "/api":
                    self._reply(404, b"", "text/plain")
                    return
                try:
                    length = min(int(self.headers.get("Content-Length", 0)), 10000)
                    data = json.loads(self.rfile.read(length) or b"{}")
                except (ValueError, json.JSONDecodeError):
                    self._reply(400, b"{}", "application/json")
                    return
                if not secrets.compare_digest(str(data.get("pin", "")), remote.pin):
                    self._reply(403, b"{}", "application/json")
                    return
                state = remote.handle(str(data.get("action", "")), str(data.get("value", ""))[:500])
                self._reply(200, json.dumps(state).encode(), "application/json")

        self.server = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True, name="telecommande").start()

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
