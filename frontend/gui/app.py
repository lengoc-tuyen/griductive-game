"""[D1] Web Server & REST API connecting GameEngine to the Web Frontend (D2).

Provides:
- ``GriductiveWebService``: Stateful API controller for the core game loop:
    * ``GET  /api/puzzles`` : List available puzzle files
    * ``GET  /api/state``   : Return current public board/card state
    * ``POST /api/load``    : Load a puzzle by path or uploaded JSON object
    * ``POST /api/restart`` : Reset current puzzle to initial state
    * ``POST /api/verdict`` : Submit a player verdict (INNOCENT / CRIMINAL)
- ``/dev``: Built-in D1 Interactive Test Console (also served at ``/`` before D2
  adds ``frontend/assets/index.html``).

-------------------------------------------------------------------------------
INSTRUCTIONS FOR [C] (Agent / Hint / Auto-Solve owner):
To expose Hint and Auto-Solve over the Web API, add two methods to
``GriductiveWebService`` and route them in ``do_POST`` below:
1. ``POST /api/hint``:
   Call ``algorithms.agent.hint.hint(self.engine.public_state())`` to obtain the
   next ``ForcedVerdict(cell, status)`` and return ``{"ok": True, "cell": ...,
   "status": ..., "state": self.engine.serialize_state()}``.
2. ``POST /api/auto_solve`` (or ``/api/step``):
   Pass ``self.engine`` (which already implements ``EngineProtocol``) into
   ``algorithms.agent.deduction_agent.DeductionAgent().run(self.engine)`` (or
   ``next_forced(self.engine.public_state())`` + ``self.engine.submit(...)`` for
   single-step execution) and return the updated state and trace.
-------------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

from frontend.engine.game_engine import GameEngine

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = REPO_ROOT / "frontend" / "assets"
PUZZLES_DIR = REPO_ROOT / "data" / "puzzles"
FIXTURES_DIR = REPO_ROOT / "algorithms" / "tests" / "fixtures"
DEFAULT_PUZZLE = FIXTURES_DIR / "puzzle_3x3_basic.json"


class GriductiveWebService:
    """Backend service managing the active ``GameEngine`` instance and JSON API responses."""

    def __init__(self, initial_puzzle_path: Optional[Path] = None) -> None:
        self._lock = threading.Lock()
        target = initial_puzzle_path or self._find_default_puzzle()
        self.engine = GameEngine.from_file(target)

    @staticmethod
    def _find_default_puzzle() -> Path:
        if PUZZLES_DIR.exists():
            for p in sorted(PUZZLES_DIR.rglob("*.json")):
                return p
        return DEFAULT_PUZZLE

    def list_puzzles(self) -> list[dict[str, Any]]:
        """Discover all available JSON puzzles in ``data/puzzles/`` and ``fixtures/``."""
        items: list[dict[str, Any]] = []
        seen_paths: set[Path] = set()
        search_roots = [PUZZLES_DIR, FIXTURES_DIR]

        for root in search_roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*.json")):
                resolved = path.resolve()
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)
                try:
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                    rel = path.relative_to(REPO_ROOT).as_posix()
                    pid = str(data.get("id") or path.stem)
                    size = int(data.get("size", 0))
                    items.append(
                        {
                            "id": pid,
                            "name": f"{pid} ({size}x{size})",
                            "size": size,
                            "path": rel,
                        }
                    )
                except Exception:
                    continue
        return items

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return {"ok": True, "state": self.engine.serialize_state()}

    def load_puzzle(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            if isinstance(payload.get("puzzle"), Mapping):
                self.engine = GameEngine.from_dict(payload["puzzle"])
                return {
                    "ok": True,
                    "message": f"Loaded custom puzzle '{self.engine.puzzle_id}'.",
                    "state": self.engine.serialize_state(),
                }

            raw_path = payload.get("path")
            if not raw_path or not isinstance(raw_path, str):
                raise ValueError("Missing 'path' or 'puzzle' object in request body.")

            candidate = Path(raw_path)
            if not candidate.is_absolute():
                candidate = (REPO_ROOT / candidate).resolve()
            else:
                candidate = candidate.resolve()

            if not candidate.exists():
                alt = (PUZZLES_DIR / raw_path).resolve()
                if alt.exists():
                    candidate = alt
                else:
                    raise FileNotFoundError(f"Puzzle file not found: {raw_path}")

            self.engine = GameEngine.from_file(candidate)
            return {
                "ok": True,
                "message": f"Loaded puzzle '{self.engine.puzzle_id}'.",
                "state": self.engine.serialize_state(),
            }

    def restart(self) -> dict[str, Any]:
        with self._lock:
            self.engine.restart()
            return {
                "ok": True,
                "message": "Puzzle restarted to initial state.",
                "state": self.engine.serialize_state(),
            }

    def submit_verdict(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        cell = payload.get("cell")
        status = payload.get("status")
        if not cell or not status:
            raise ValueError("Request body must include 'cell' and 'status'.")
        with self._lock:
            outcome = self.engine.submit_verdict(str(cell), str(status))
            res = outcome.to_dict()
            res["ok"] = True
            res["state"] = self.engine.serialize_state()
            return res

    # TODO [For C - Deduction Agent owner]:
    # Add `get_hint(self)` and `auto_solve(self)` / `step_agent(self)` here by calling
    # `algorithms.agent.hint.hint(self.engine.public_state())` and
    # `algorithms.agent.deduction_agent.DeductionAgent().run(self.engine)`.


# ---------------------------------------------------------------------------
# Built-in D1 Developer Test Console (used when D2 hasn't created index.html yet,
# or accessible anytime at http://127.0.0.1:5000/dev)
# ---------------------------------------------------------------------------
_DEV_CONSOLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Griductive — D1 Engine & Web API Test Console</title>
  <style>
    :root {
      --bg: #F4F0E8;
      --ink: #262420;
      --card-down: #FAF7F2;
      --innocent-bg: #EAF5EE;
      --innocent-border: #22C55E;
      --criminal-bg: #FDE8E7;
      --criminal-border: #E0564B;
      --highlight: #F59E0B;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 24px;
      border-bottom: 2px solid #dcd6c8;
      background: #efeae0;
      flex-wrap: wrap;
      gap: 10px;
    }
    .brand {
      font-family: Georgia, serif;
      font-size: 22px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .badge {
      font-family: monospace;
      font-size: 11px;
      background: #262420;
      color: #fff;
      padding: 3px 8px;
      border-radius: 999px;
    }
    .toolbar {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    select, button, .file-btn {
      font-family: inherit;
      font-size: 13px;
      padding: 7px 13px;
      border: 2px solid var(--ink);
      border-radius: 999px;
      background: #FAF7F2;
      color: var(--ink);
      font-weight: 600;
      cursor: pointer;
      box-shadow: 2px 2px 0 var(--ink);
      transition: transform 0.08s ease;
    }
    button:active, .file-btn:active { transform: translate(2px, 2px); box-shadow: none; }
    .container {
      display: grid;
      grid-template-columns: minmax(340px, 1.15fr) minmax(320px, 0.85fr);
      gap: 24px;
      padding: 20px 24px;
      max-width: 1320px;
      margin: 0 auto;
    }
    @media (max-width: 900px) {
      .container { grid-template-columns: 1fr; }
    }
    .board-wrap {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 14px;
    }
    .banner {
      width: 100%;
      padding: 10px 14px;
      border-radius: 10px;
      border: 2px solid var(--ink);
      font-size: 13px;
      font-weight: 600;
      background: #FAF7F2;
    }
    .banner.ACCEPTED { background: var(--innocent-bg); border-color: var(--innocent-border); color: #14532d; }
    .banner.NOT_PROVABLE { background: #FEF3C7; border-color: #D97706; color: #78350F; }
    .banner.CONTRADICTED { background: var(--criminal-bg); border-color: var(--criminal-border); color: #7F1D1D; }
    .grid {
      display: grid;
      gap: 10px;
      width: 100%;
      max-width: 600px;
    }
    .card {
      background: var(--card-down);
      border: 2px solid var(--ink);
      border-radius: 12px;
      padding: 10px;
      min-height: 138px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      cursor: pointer;
      position: relative;
      transition: transform 0.12s ease, opacity 0.15s ease, box-shadow 0.15s ease;
    }
    .card:hover { transform: translateY(-2px); }
    .card.INNOCENT { background: var(--innocent-bg); border-color: var(--innocent-border); }
    .card.CRIMINAL { background: var(--criminal-bg); border-color: var(--criminal-border); }
    .card.highlighted { box-shadow: 0 0 0 4px var(--highlight); }
    .card.dimmed { opacity: 0.42; }
    .card-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-family: monospace;
      font-size: 11px;
      font-weight: 700;
      color: #57534e;
    }
    .card-center { text-align: center; margin: 6px 0; }
    .avatar-circle {
      width: 38px;
      height: 38px;
      border-radius: 50%;
      margin: 0 auto 5px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 15px;
      color: #fff;
      border: 1.5px solid var(--ink);
    }
    .card-name { font-size: 15px; font-weight: 700; }
    .card-prof { font-family: monospace; font-size: 10px; color: #57534e; text-transform: uppercase; }
    .card-clue {
      font-size: 12px;
      line-height: 1.25;
      text-align: center;
      padding: 4px 2px;
      font-weight: 500;
    }
    .status-pill {
      font-family: monospace;
      font-size: 10px;
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: 700;
    }
    .status-pill.INNOCENT { background: #bbf7d0; color: #14532d; }
    .status-pill.CRIMINAL { background: #fecaca; color: #7f1d1d; }
    .panel {
      background: #FAF7F2;
      border: 2px solid var(--ink);
      border-radius: 12px;
      padding: 14px;
      margin-bottom: 14px;
    }
    .panel h3 {
      margin: 0 0 10px 0;
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    pre {
      background: #1e1e1e;
      color: #d4d4d4;
      padding: 12px;
      border-radius: 8px;
      font-size: 11.5px;
      max-height: 420px;
      overflow: auto;
      margin: 0;
    }
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.55);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 50;
    }
    .modal-backdrop.open { display: flex; }
    .modal {
      background: #FAF7F2;
      border: 2px solid var(--ink);
      border-radius: 16px;
      padding: 22px;
      width: 320px;
      text-align: center;
      box-shadow: 4px 4px 0 var(--ink);
    }
    .modal h2 { margin: 8px 0 4px; font-size: 19px; }
    .modal p { margin: 0 0 16px; font-size: 13px; color: #57534e; }
    .modal-actions {
      display: flex;
      gap: 10px;
      justify-content: center;
      margin-bottom: 10px;
    }
    .btn-innocent { background: #38A169; color: #fff; border-color: #14532d; flex: 1; }
    .btn-criminal { background: #E53E3E; color: #fff; border-color: #7f1d1d; flex: 1; }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span>🕵️ Griductive</span>
      <span class="badge">D1 Engine & API Test Console</span>
    </div>
    <div class="toolbar">
      <select id="puzzleSelect" title="Select puzzle"></select>
      <label class="file-btn">
        📂 Upload JSON
        <input type="file" id="fileInput" accept=".json" style="display:none" />
      </label>
      <button onclick="apiRestart()">↺ Restart</button>
    </div>
  </header>

  <div class="container">
    <div class="board-wrap">
      <div id="banner" class="banner">
        Click any face-down card to call INNOCENT or CRIMINAL, or click a revealed card to highlight its clue region.
      </div>
      <div id="grid" class="grid"></div>
    </div>

    <div>
      <div class="panel">
        <h3>📌 Puzzle Progress</h3>
        <div style="font-family:monospace;font-size:14px;">
          Puzzle ID: <strong id="stId">-</strong> &nbsp;|&nbsp;
          Revealed: <strong id="stSolved">0/0</strong>
        </div>
      </div>

      <div class="panel">
        <h3>🔌 Last API JSON Response (D1 ↔ D2 Contract)</h3>
        <pre id="jsonOut">{}</pre>
      </div>
    </div>
  </div>

  <div id="modalBackdrop" class="modal-backdrop" onclick="if(event.target===this)closeModal()">
    <div class="modal">
      <div id="modalCoord" style="font-family:monospace;font-weight:700;font-size:12px;">A1</div>
      <h2 id="modalName">Suspect</h2>
      <p id="modalProf">Profession</p>
      <p style="font-weight:600;color:#262420;">Innocent or criminal?</p>
      <div class="modal-actions">
        <button class="btn-innocent" onclick="submitVerdict('INNOCENT')">✓ Innocent</button>
        <button class="btn-criminal" onclick="submitVerdict('CRIMINAL')">✕ Criminal</button>
      </div>
      <button onclick="closeModal()" style="width:100%;">Cancel</button>
    </div>
  </div>

  <script>
    let currentState = null;
    let activeHighlight = [];
    let activeClueOwner = null;
    let modalCell = null;

    const COLORS = ["#8B5CF6", "#EC4899", "#0EA5E9", "#10B981", "#F59E0B", "#6366F1", "#14B8A6", "#F97316"];
    function colorFor(name) {
      let h = 0;
      for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
      return COLORS[h % COLORS.length];
    }

    function showJson(data) {
      document.getElementById("jsonOut").textContent = JSON.stringify(data, null, 2);
    }

    function setBanner(text, kind = "") {
      const b = document.getElementById("banner");
      b.className = "banner " + kind;
      b.textContent = text;
    }

    async function loadPuzzleList() {
      const res = await fetch("/api/puzzles");
      const data = await res.json();
      const sel = document.getElementById("puzzleSelect");
      sel.innerHTML = "";
      (data.puzzles || []).forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.path;
        opt.textContent = p.name + " — " + p.path;
        sel.appendChild(opt);
      });
      sel.onchange = () => apiLoadPath(sel.value);
    }

    async function fetchState() {
      const res = await fetch("/api/state");
      const data = await res.json();
      showJson(data);
      if (data.state) renderState(data.state);
    }

    async function apiLoadPath(path) {
      const res = await fetch("/api/load", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({path})
      });
      const data = await res.json();
      showJson(data);
      activeHighlight = [];
      activeClueOwner = null;
      if (data.state) renderState(data.state);
      setBanner(data.message || "Loaded puzzle.");
    }

    document.getElementById("fileInput").addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        const text = await file.text();
        const puzzle = JSON.parse(text);
        const res = await fetch("/api/load", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({puzzle})
        });
        const data = await res.json();
        showJson(data);
        activeHighlight = [];
        activeClueOwner = null;
        if (data.state) renderState(data.state);
        setBanner(data.message || "Loaded uploaded JSON.");
      } catch (err) {
        setBanner("Invalid JSON file: " + err, "CONTRADICTED");
      }
    });

    async function apiRestart() {
      const res = await fetch("/api/restart", {method: "POST"});
      const data = await res.json();
      showJson(data);
      activeHighlight = [];
      activeClueOwner = null;
      if (data.state) renderState(data.state);
      setBanner(data.message || "Restarted.");
    }

    function openModal(card) {
      modalCell = card.cell;
      document.getElementById("modalCoord").textContent = card.cell;
      document.getElementById("modalName").textContent = card.name;
      document.getElementById("modalProf").textContent = card.profession;
      document.getElementById("modalBackdrop").classList.add("open");
    }

    function closeModal() {
      modalCell = null;
      document.getElementById("modalBackdrop").classList.remove("open");
    }

    async function submitVerdict(status) {
      if (!modalCell) return;
      const cell = modalCell;
      closeModal();
      const res = await fetch("/api/verdict", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({cell, status})
      });
      const data = await res.json();
      showJson(data);
      if (data.revealed_clue && data.revealed_clue.highlight_cells) {
        activeClueOwner = cell;
        activeHighlight = data.revealed_clue.highlight_cells;
      }
      if (data.state) renderState(data.state);
      setBanner(data.message, data.result);
    }

    function onCardClick(card) {
      if (!card.is_revealed) {
        openModal(card);
        return;
      }
      if (activeClueOwner === card.cell) {
        activeClueOwner = null;
        activeHighlight = [];
      } else {
        activeClueOwner = card.cell;
        activeHighlight = card.highlight_cells || [];
      }
      renderState(currentState);
    }

    function renderState(state) {
      currentState = state;
      const grid = document.getElementById("grid");
      grid.style.gridTemplateColumns = `repeat(${state.size}, 1fr)`;
      grid.innerHTML = "";

      const hasHighlight = activeHighlight.length > 0;
      state.cards.forEach(card => {
        const el = document.createElement("div");
        let cls = "card";
        if (card.is_revealed && card.status) cls += " " + card.status;
        if (activeHighlight.includes(card.cell)) cls += " highlighted";
        if (hasHighlight && !activeHighlight.includes(card.cell) && activeClueOwner !== card.cell) {
          cls += " dimmed";
        }
        el.className = cls;
        el.onclick = () => onCardClick(card);

        const icon = card.is_revealed ? (activeClueOwner === card.cell ? "🔍" : "") : "";
        if (!card.is_revealed) {
          el.innerHTML = `
            <div class="card-top"><span>${card.cell}</span><span></span></div>
            <div class="card-center">
              <div class="avatar-circle" style="background:${colorFor(card.name)}">${card.name[0]}</div>
              <div class="card-name">${card.name}</div>
              <div class="card-prof">${card.profession}</div>
            </div>
            <div style="font-size:10px;text-align:center;color:#78716c;">Tap to call</div>
          `;
        } else {
          el.innerHTML = `
            <div class="card-top">
              <span>${card.cell} · <strong>${card.name}</strong> (${card.profession})</span>
              <span>${icon}</span>
            </div>
            <div class="card-clue">${card.clue_text || "(No clue)"}</div>
            <div style="text-align:center;">
              <span class="status-pill ${card.status}">${card.status}</span>
            </div>
          `;
        }
        grid.appendChild(el);
      });

      document.getElementById("stId").textContent = state.puzzle_id;
      document.getElementById("stSolved").textContent =
        `${state.proved_count}/${state.total_cells}` + (state.is_solved ? " 🎉 SOLVED!" : "");
    }

    loadPuzzleList().then(fetchState);
  </script>
</body>
</html>
"""


def _make_handler(service: GriductiveWebService):
    class GriductiveRequestHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            pass

        def _send_json(self, status: int, data: Mapping[str, Any]) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, status: int, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw) if raw.strip() else {}

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            route = parsed.path

            if route == "/api/puzzles":
                self._send_json(HTTPStatus.OK, {"ok": True, "puzzles": service.list_puzzles()})
                return

            if route == "/api/state":
                self._send_json(HTTPStatus.OK, service.get_state())
                return

            if route == "/dev":
                self._send_html(HTTPStatus.OK, _DEV_CONSOLE_HTML)
                return

            # Serve D2's static files from frontend/assets/ if available
            rel_path = "index.html" if route in ("", "/") else route.lstrip("/")
            asset_file = (ASSETS_DIR / rel_path).resolve()

            if str(asset_file).startswith(str(ASSETS_DIR.resolve())) and asset_file.is_file():
                mime, _ = mimetypes.guess_type(str(asset_file))
                content = asset_file.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mime or "application/octet-stream")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

            # Fallback to D1 Test Console if D2's index.html is not present yet
            if route in ("", "/"):
                self._send_html(HTTPStatus.OK, _DEV_CONSOLE_HTML)
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": f"Not found: {route}"})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            route = parsed.path
            try:
                payload = self._read_json_body()
                if route == "/api/load":
                    self._send_json(HTTPStatus.OK, service.load_puzzle(payload))
                elif route == "/api/restart":
                    self._send_json(HTTPStatus.OK, service.restart())
                elif route == "/api/verdict":
                    self._send_json(HTTPStatus.OK, service.submit_verdict(payload))
                # TODO [For C - Deduction Agent owner]:
                # Wire `/api/hint` and `/api/auto_solve` (or `/api/step`) here.
                else:
                    self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": f"Unknown API endpoint: {route}"})
            except Exception as exc:  # noqa: BLE001
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                )

    return GriductiveRequestHandler


def create_http_server(
    host: str = "127.0.0.1",
    port: int = 5000,
    puzzle_path: Optional[Path] = None,
) -> tuple[ThreadingHTTPServer, GriductiveWebService]:
    """Create a ``ThreadingHTTPServer`` and its ``GriductiveWebService``."""
    service = GriductiveWebService(initial_puzzle_path=puzzle_path)
    server = ThreadingHTTPServer((host, port), _make_handler(service))
    return server, service


def run_server(
    host: str = "127.0.0.1",
    port: int = 5000,
    puzzle_path: Optional[Path] = None,
    open_browser: bool = True,
) -> None:
    """Start the Griductive Web Server and optionally open the browser."""
    server, service = create_http_server(host=host, port=port, puzzle_path=puzzle_path)
    actual_port = server.server_port
    url = f"http://{host}:{actual_port}"
    has_d2_ui = (ASSETS_DIR / "index.html").is_file()
    mode_note = "D2 Knotwise UI (frontend/assets/index.html)" if has_d2_ui else "Built-in D1 Test Console (/dev)"

    print(f"Griductive Web Server running at {url}")
    print(f"Active puzzle : {service.engine.puzzle_id} ({service.engine.board.size}x{service.engine.board.size})")
    print(f"Frontend mode : {mode_note}")
    print(f"D1 Test UI    : {url}/dev")
    print("Press Ctrl+C to stop.")

    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Griductive Web Server...")
    finally:
        server.server_close()
