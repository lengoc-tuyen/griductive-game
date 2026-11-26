"""[D1] Web Server & REST API connecting GameEngine to the Web Frontend (D2).

Provides:
- ``GriductiveWebService``: Stateful API controller for the core game loop:
    * ``GET  /api/puzzles`` : List available puzzle files
    * ``GET  /api/state``   : Return current public board/card state
    * ``POST /api/load``    : Load a puzzle by path or uploaded JSON object
    * ``POST /api/restart`` : Reset current puzzle to initial state
    * ``POST /api/verdict`` : Submit a player verdict (INNOCENT / CRIMINAL)
    * ``POST /api/hint``    : Suggest the next forced verdict (no state change)
    * ``POST /api/step``    : Apply a single deduced verdict
    * ``POST /api/auto_solve`` : Run the deduction agent until solved or stuck
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

from algorithms.agent.deduction_agent import AgentOutcome, DeductionAgent
from algorithms.agent.hint import hint as compute_hint
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
        diff_rank = {"basic": 0, "easy": 1, "medium": 2, "hard": 3, "ext": 4}

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
                    low = pid.lower()
                    difficulty = "custom"
                    for d in ("easy", "medium", "hard", "ext", "basic"):
                        if d in low:
                            difficulty = d
                            break
                    label = pid.replace("puzzle_", "").replace("_", " ").title()
                    items.append(
                        {
                            "id": pid,
                            "name": f"{label} ({size}x{size})",
                            "size": size,
                            "difficulty": difficulty,
                            "path": rel,
                        }
                    )
                except Exception:
                    continue
        items.sort(key=lambda x: (x["size"], diff_rank.get(x["difficulty"], 9), x["id"]))
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

    def get_hint(self) -> dict[str, Any]:
        """Compute the next logically forced cell + irredundant supporting clues via [C] hint()."""
        with self._lock:
            state = self.engine.public_state()
            if state.is_solved():
                return {
                    "ok": True,
                    "outcome": "SOLVED",
                    "cell": None,
                    "message": "The puzzle is already solved!",
                    "state": self.engine.serialize_state(),
                }
            try:
                h = compute_hint(state, explain=True)
            except ValueError:
                return {
                    "ok": True,
                    "outcome": "INCONSISTENT",
                    "cell": None,
                    "message": "The revealed clues are logically inconsistent (UNSAT).",
                    "state": self.engine.serialize_state(),
                }

            if h is None:
                return {
                    "ok": True,
                    "outcome": "NONE",
                    "cell": None,
                    "message": "No character is logically forced from the currently unlocked clues.",
                    "state": self.engine.serialize_state(),
                }

            clue_id_set = set(h.clue_ids)
            supporting_cells = [c.owner for c in state.revealed_clues if c.id in clue_id_set]
            ch = state.board.character_at(h.cell)
            return {
                "ok": True,
                "outcome": "FOUND",
                "cell": h.cell,
                "name": ch.name,
                "status": h.status.value,
                "clue_ids": list(h.clue_ids),
                "supporting_cells": supporting_cells,
                "proved_cells": list(h.proved_cells),
                "sat_calls": h.sat_calls,
                "message": h.message(state),
                "state": self.engine.serialize_state(),
            }

    def step_agent(self) -> dict[str, Any]:
        """Execute a single no-guess deduction step using [C] DeductionAgent(max_steps=1)."""
        with self._lock:
            if self.engine.public_state().is_solved():
                return {
                    "ok": True,
                    "outcome": "SOLVED",
                    "step": None,
                    "message": "The puzzle is already solved!",
                    "state": self.engine.serialize_state(),
                }

            run = DeductionAgent(max_steps=1, time_limit=10.0).run(self.engine)
            state_dict = self.engine.serialize_state()
            if run.steps:
                s = run.steps[0]
                ch = self.engine.board.character_at(s.cell)
                now_solved = state_dict["is_solved"]
                return {
                    "ok": True,
                    "outcome": "SOLVED" if now_solved else "STEPPED",
                    "step": {
                        **s.to_dict(),
                        "name": ch.name,
                        "sat_calls": s.sat_calls,
                    },
                    "summary": run.summary(),
                    "message": f"{ch.name} ({s.cell}) = {s.verdict.value}",
                    "state": state_dict,
                }

            reason_map = {
                AgentOutcome.STUCK: "No logically forced move remains — the agent never guesses.",
                AgentOutcome.INCONSISTENT: "The current clues contradict each other (UNSAT).",
                AgentOutcome.TIMEOUT: "The SAT solver exceeded the time limit.",
                AgentOutcome.REJECTED: "Engine rejected the agent's proposed verdict.",
            }
            return {
                "ok": True,
                "outcome": run.outcome.value,
                "step": None,
                "summary": run.summary(),
                "message": reason_map.get(run.outcome, f"Agent stopped ({run.outcome.value})."),
                "state": state_dict,
            }

    def auto_solve(self) -> dict[str, Any]:
        """Run [C] DeductionAgent to completion and return the full deduction trace."""
        with self._lock:
            run = DeductionAgent(time_limit=15.0).run(self.engine)
            steps_out = []
            for s in run.steps:
                ch = self.engine.board.character_at(s.cell)
                steps_out.append({
                    **s.to_dict(),
                    "name": ch.name,
                    "sat_calls": s.sat_calls,
                })
            return {
                "ok": True,
                "outcome": run.outcome.value,
                "steps": steps_out,
                "trace": run.trace.to_dict(),
                "summary": run.summary(),
                "state": self.engine.serialize_state(),
            }


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
                elif route == "/api/hint":
                    self._send_json(HTTPStatus.OK, service.get_hint())
                elif route == "/api/step":
                    self._send_json(HTTPStatus.OK, service.step_agent())
                elif route == "/api/auto_solve":
                    self._send_json(HTTPStatus.OK, service.auto_solve())
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

    print(f"Griductive Web Server running at {url}")
    print(f"Active puzzle : {service.engine.puzzle_id} ({service.engine.board.size}x{service.engine.board.size})")
    print("Press Ctrl+C to stop.")

    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Griductive Web Server...")
    finally:
        server.server_close()
