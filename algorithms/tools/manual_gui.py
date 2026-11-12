"""Minimal Tkinter GUI for manually testing the algorithms.

This is a DEV TOOL, not the official game GUI (that belongs to frontend/, owned by D).

Run from the repo root:
    python -m algorithms.tools.manual_gui [path/to/puzzle.json]

Without an argument it opens algorithms/tests/fixtures/puzzle_3x3_basic.json.

Usage
-----
* Click a face-down card to select it, then press CRIMINAL / INNOCENT.
* Click a face-up card (or a clue in the list) to highlight the cells that clue refers to.
* Hint      : the agent names one provable cell (public knowledge only).
* Step      : the agent plays one forced verdict.
* Auto Solve: the agent plays until solved / stuck / inconsistent.
* "Agent view" shows what the agent currently deduces for every hidden card.
"""

from __future__ import annotations

import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Mapping, Optional

from algorithms.agent.deduction_agent import find_forced
from algorithms.agent.entailment import Classification, check_verdict, classify_all
from algorithms.agent.hint import hint
from algorithms.agent.knowledge_base import build_kb
from algorithms.agent.public_state import PublicState, VerdictResult
from algorithms.logic.clues import referenced_cells
from algorithms.logic.models import Board, Clue, ClueType, Status

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PUZZLE = REPO_ROOT / "algorithms" / "tests" / "fixtures" / "puzzle_3x3_basic.json"

# colours
BG = "#f5f1ea"
FACE_DOWN = "#dcd7cf"
CRIMINAL_BG = "#f3c4bf"
INNOCENT_BG = "#c9e7cb"
SELECT = "#1e6fd9"
HIGHLIGHT = "#f2a900"
NORMAL_BORDER = "#9b948a"


# ---------------------------------------------------------------- engine (dev only)
class ManualEngine:
    """Owns the full puzzle; hands out only PublicState (same contract as EngineProtocol)."""

    def __init__(self, puzzle: Mapping[str, Any]) -> None:
        self.puzzle_id = puzzle.get("id", "?")
        self.board = Board.from_dict(puzzle)
        self._solution = {c: Status(s) for c, s in puzzle["solution"].items()}
        self._clue_of = {}
        for d in puzzle.get("clues", []):
            clue = Clue.from_dict(d)
            self._clue_of[clue.owner] = clue
        self._initial = list(puzzle.get("initially_revealed", []))
        self.warnings: list[str] = []
        self.restart()

    def restart(self) -> None:
        self._proved = {c: self._solution[c] for c in self._initial}
        self._revealed = [self._clue_of[c] for c in self._initial if c in self._clue_of]

    def public_state(self) -> PublicState:
        return PublicState(self.board, tuple(self._revealed), dict(self._proved))

    def submit(self, cell: str, status: Status) -> tuple[VerdictResult, Optional[Clue]]:
        result = check_verdict(self.public_state(), cell, status)
        if result is not VerdictResult.ACCEPTED or cell in self._proved:
            return result, None
        if self._solution[cell] is not status:
            self.warnings.append(f"{cell}: proved {status.value} but solution says "
                                 f"{self._solution[cell].value} (puzzle is not unique?)")
        self._proved[cell] = status
        clue = self._clue_of.get(cell)
        if clue is not None:
            self._revealed.append(clue)
        return result, clue


# ------------------------------------------------------------------- clue -> text
def region_text(region: Mapping[str, Any]) -> str:
    kind = region.get("kind")
    if kind == "row":
        return f"row {region['row']}"
    if kind == "col":
        return f"column {region['col']}"
    if kind == "neighbors":
        return f"the neighbors of {region['of']}"
    if kind == "cells":
        return "{" + ", ".join(region["cells"]) + "}"
    if kind == "corners":
        return "the corners"
    if kind == "edges":
        return "the edges"
    if kind == "between":
        return f"the cells between {region['a']} and {region['b']}"
    if kind == "common_neighbors":
        return f"the common neighbors of {region['a']} and {region['b']}"
    return str(region)


def clue_text(clue: Clue) -> str:
    p = clue.params
    if clue.type is ClueType.FACT:
        return f"{p['person']} is {p['status'].lower()}"
    if clue.type is ClueType.SAME:
        return f"{p['a']} and {p['b']} have the same status"
    if clue.type is ClueType.DIFFERENT:
        return f"{p['a']} and {p['b']} have different statuses"
    noun = clue.counted_status.value.lower()  # "criminal" / "innocent"
    if clue.type is ClueType.PARITY:
        return f"An {p['parity'].lower()} number of {noun}s in {region_text(p['region'])}"
    if clue.type is ClueType.COMPARE:
        op = {"MORE": "More", "FEWER": "Fewer", "EQUAL": "As many"}[p["op"]]
        joiner = "as" if p["op"] == "EQUAL" else "than"
        return f"{op} {noun}s in {region_text(p['region_a'])} {joiner} in {region_text(p['region_b'])}"
    word = {ClueType.EXACTLY: "Exactly", ClueType.AT_LEAST: "At least", ClueType.AT_MOST: "At most"}[clue.type]
    k = p["k"]
    if clue.type in (ClueType.EXACTLY, ClueType.AT_MOST) and k == 0:
        return f"No {noun}s in {region_text(p['region'])}"
    return f"{word} {k} {noun}{'s' if k != 1 else ''} in {region_text(p['region'])}"


# ------------------------------------------------------------------------- widgets
class Card(tk.Frame):
    W, H = 160, 118

    def __init__(self, master, cell: str, on_click) -> None:
        super().__init__(master, width=self.W, height=self.H, bg=FACE_DOWN,
                         highlightthickness=3, highlightbackground=NORMAL_BORDER)
        self.pack_propagate(False)
        self.cell = cell
        self.lbl_coord = tk.Label(self, text=cell, font=("Segoe UI", 8), anchor="w")
        self.lbl_name = tk.Label(self, font=("Segoe UI", 11, "bold"))
        self.lbl_prof = tk.Label(self, font=("Segoe UI", 8, "italic"))
        self.lbl_status = tk.Label(self, font=("Segoe UI", 9, "bold"))
        self.lbl_clue = tk.Label(self, font=("Segoe UI", 8), wraplength=self.W - 14, justify="center")
        self.lbl_coord.pack(fill="x", padx=4)
        for w in (self.lbl_name, self.lbl_prof, self.lbl_status, self.lbl_clue):
            w.pack()
        for w in (self, *self.winfo_children()):
            w.bind("<Button-1>", lambda _e: on_click(cell))

    def render(self, name: str, profession: str, status: Optional[Status], clue: Optional[str],
               agent_view: Optional[Classification], selected: bool, highlighted: bool) -> None:
        if status is Status.CRIMINAL:
            bg, st, fg = CRIMINAL_BG, "CRIMINAL", "#a1261b"
        elif status is Status.INNOCENT:
            bg, st, fg = INNOCENT_BG, "INNOCENT", "#1f6b2a"
        else:
            bg, st, fg = FACE_DOWN, "", "#555"
            if agent_view is not None:
                st = {Classification.CRIMINAL: "agent: → CRIMINAL",
                      Classification.INNOCENT: "agent: → INNOCENT",
                      Classification.UNKNOWN: "agent: ?",
                      Classification.INCONSISTENT: "agent: INCONSISTENT"}[agent_view]
        border = SELECT if selected else HIGHLIGHT if highlighted else NORMAL_BORDER
        self.configure(bg=bg, highlightbackground=border, highlightcolor=border)
        for w in self.winfo_children():
            w.configure(bg=bg)
        self.lbl_name.configure(text=name)
        self.lbl_prof.configure(text=profession)
        self.lbl_status.configure(text=st, fg=fg)
        self.lbl_clue.configure(text=clue or ("" if status else "(face down)"))


class ManualGUI:
    def __init__(self, root: tk.Tk, puzzle_path: Path) -> None:
        self.root = root
        self.engine: Optional[ManualEngine] = None
        self.cards: dict[str, Card] = {}
        self.selected: Optional[str] = None
        self.highlighted: set[str] = set()
        self.auto_running = False
        self.agent_view = tk.BooleanVar(value=False)
        self.total_sat_calls = 0

        root.title("Griductive – manual test (dev tool)")
        root.configure(bg=BG)
        self._build_layout()
        self.load(puzzle_path)

    # ---------------------------------------------------------------- layout
    def _build_layout(self) -> None:
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=8, pady=6)
        for text, cmd in (("Load…", self.on_load), ("Restart", self.on_restart), ("Hint", self.on_hint),
                          ("Step", self.on_step), ("Auto Solve", self.on_auto)):
            tk.Button(bar, text=text, command=cmd, width=10).pack(side="left", padx=2)
        tk.Checkbutton(bar, text="Agent view", variable=self.agent_view, bg=BG,
                       command=self.refresh).pack(side="left", padx=10)
        self.lbl_puzzle = tk.Label(bar, bg=BG, font=("Segoe UI", 9))
        self.lbl_puzzle.pack(side="right")

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=8, pady=4)
        self.board_frame = tk.Frame(body, bg=BG)
        self.board_frame.pack(side="left", anchor="n")

        side = tk.Frame(body, bg=BG)
        side.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.lbl_selected = tk.Label(side, text="Select a card", bg=BG, font=("Segoe UI", 10, "bold"), anchor="w")
        self.lbl_selected.pack(fill="x")
        btns = tk.Frame(side, bg=BG)
        btns.pack(fill="x", pady=4)
        tk.Button(btns, text="CRIMINAL", bg=CRIMINAL_BG, width=12,
                  command=lambda: self.on_verdict(Status.CRIMINAL)).pack(side="left", padx=2)
        tk.Button(btns, text="INNOCENT", bg=INNOCENT_BG, width=12,
                  command=lambda: self.on_verdict(Status.INNOCENT)).pack(side="left", padx=2)

        tk.Label(side, text="Revealed clues (click to highlight)", bg=BG, anchor="w").pack(fill="x", pady=(8, 0))
        self.clue_list = tk.Listbox(side, height=8, width=58, activestyle="none")
        self.clue_list.pack(fill="x")
        self.clue_list.bind("<<ListboxSelect>>", self.on_clue_list_select)

        tk.Label(side, text="Log", bg=BG, anchor="w").pack(fill="x", pady=(8, 0))
        self.log_box = tk.Text(side, height=16, width=58, font=("Consolas", 9), state="disabled")
        self.log_box.pack(fill="both", expand=True)

        self.status_bar = tk.Label(self.root, anchor="w", bg="#e7e1d6", font=("Segoe UI", 9))
        self.status_bar.pack(fill="x", side="bottom")

    def _build_board(self) -> None:
        for w in self.board_frame.winfo_children():
            w.destroy()
        self.cards.clear()
        n = self.engine.board.size
        for c in range(n):
            tk.Label(self.board_frame, text=chr(ord("A") + c), bg=BG,
                     font=("Segoe UI", 10, "bold")).grid(row=0, column=c + 1)
        for r in range(n):
            tk.Label(self.board_frame, text=str(r + 1), bg=BG,
                     font=("Segoe UI", 10, "bold")).grid(row=r + 1, column=0, padx=4)
            for c in range(n):
                cell = f"{chr(ord('A') + c)}{r + 1}"
                card = Card(self.board_frame, cell, self.on_card_click)
                card.grid(row=r + 1, column=c + 1, padx=3, pady=3)
                self.cards[cell] = card

    # ---------------------------------------------------------------- helpers
    def log(self, msg: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def status(self, msg: str) -> None:
        self.status_bar.configure(text=" " + msg)

    def state(self) -> PublicState:
        return self.engine.public_state()

    def revealed_clue_at(self, cell: str) -> Optional[Clue]:
        for clue in self.state().revealed_clues:
            if clue.owner == cell:
                return clue
        return None

    def refresh(self) -> None:
        state = self.state()
        view: dict[str, Classification] = {}
        if self.agent_view.get() and not state.is_solved():
            kb = build_kb(state)
            view = classify_all(kb)
            self.total_sat_calls += kb.sat_calls
        for cell, card in self.cards.items():
            ch = state.board.character_at(cell)
            clue = self.revealed_clue_at(cell)
            card.render(ch.name, ch.profession, state.proved.get(cell),
                        clue_text(clue) if clue else None, view.get(cell),
                        cell == self.selected, cell in self.highlighted)
        self.clue_list.delete(0, "end")
        for clue in state.revealed_clues:
            self.clue_list.insert("end", f"[{clue.owner}] {clue_text(clue)}")
        solved = len(state.proved)
        total = state.board.size ** 2
        self.status(f"Proved {solved}/{total}   ·   SAT calls so far: {self.total_sat_calls}"
                    + ("   ·   SOLVED 🎉" if state.is_solved() else ""))
        for w in self.engine.warnings:
            self.log("WARNING " + w)
        self.engine.warnings.clear()

    def highlight_clue(self, clue: Optional[Clue]) -> None:
        if clue is None:
            self.highlighted = set()
            return
        try:
            self.highlighted = set(referenced_cells(clue, self.engine.board))
        except ValueError as e:
            self.highlighted = set()
            self.log(f"bad clue {clue.id}: {e}")

    # ---------------------------------------------------------------- actions
    def load(self, path: Path) -> None:
        try:
            with open(path, encoding="utf-8") as f:
                puzzle = json.load(f)
            engine = ManualEngine(puzzle)
            for clue in engine._clue_of.values():  # validate every clue up front
                referenced_cells(clue, engine.board)
        except Exception as e:  # noqa: BLE001 - show any load error to the user
            messagebox.showerror("Load failed", f"{path}\n\n{type(e).__name__}: {e}")
            return
        self.auto_running = False
        self.engine = engine
        self.selected, self.highlighted = None, set()
        self.total_sat_calls = 0
        self.lbl_puzzle.configure(text=f"{engine.puzzle_id}  ({path.name})")
        self._build_board()
        self.log(f"Loaded {path.name}: {engine.board.size}x{engine.board.size}, "
                 f"{len(engine._clue_of)} clues, revealed {engine._initial}")
        self.refresh()

    def on_load(self) -> None:
        start = REPO_ROOT / "data" / "puzzles"
        if not start.exists():
            start = DEFAULT_PUZZLE.parent
        path = filedialog.askopenfilename(initialdir=start, filetypes=[("Puzzle JSON", "*.json")])
        if path:
            self.load(Path(path))

    def on_restart(self) -> None:
        self.auto_running = False
        self.engine.restart()
        self.selected, self.highlighted = None, set()
        self.total_sat_calls = 0
        self.log("— restart —")
        self.refresh()

    def on_card_click(self, cell: str) -> None:
        self.selected = cell
        ch = self.engine.board.character_at(cell)
        status = self.state().proved.get(cell)
        clue = self.revealed_clue_at(cell)
        self.highlight_clue(clue)
        self.lbl_selected.configure(text=f"{cell}  {ch.name} ({ch.profession})"
                                         + (f"  —  {status.value}" if status else "  —  face down"))
        self.refresh()

    def on_clue_list_select(self, _event) -> None:
        sel = self.clue_list.curselection()
        if not sel:
            return
        clue = self.state().revealed_clues[sel[0]]
        self.highlight_clue(clue)
        self.log(f"clue {clue.id} refers to {sorted(self.highlighted)}")
        self.refresh()

    def on_verdict(self, status: Status) -> None:
        cell = self.selected
        if cell is None:
            self.status("Select a card first")
            return
        if cell in self.state().proved:
            self.status(f"{cell} is already revealed")
            return
        result, clue = self.engine.submit(cell, status)
        if result is VerdictResult.ACCEPTED:
            self.log(f"YOU  {cell} = {status.value}  ✓  revealed: "
                     + (clue_text(clue) if clue else "(no clue)"))
            self.highlight_clue(clue)
        elif result is VerdictResult.NOT_PROVABLE:
            self.log(f"YOU  {cell} = {status.value}  ✗  NOT_PROVABLE (neither status is forced yet)")
        else:
            self.log(f"YOU  {cell} = {status.value}  ✗  CONTRADICTED (the opposite status is forced)")
        self.refresh()

    def _agent_move(self) -> Optional[str]:
        """Play one forced verdict. Returns None if a move was made, else a stop reason."""
        state = self.state()
        if state.is_solved():
            return "SOLVED"
        kb = build_kb(state)
        try:
            forced = find_forced(kb)
        except ValueError:
            forced = None
            self.total_sat_calls += kb.sat_calls
            return "INCONSISTENT"
        self.total_sat_calls += kb.sat_calls
        if forced is None:
            return "STUCK (nothing is forced - the agent will not guess)"
        result, clue = self.engine.submit(forced.cell, forced.status)
        if result is not VerdictResult.ACCEPTED:
            return f"REJECTED by engine: {result.value}"
        s = kb.stats
        self.log(f"AGENT {forced.cell} = {forced.status.value}   [sat={kb.sat_calls} dec={s.decisions} "
                 f"prop={s.propagations} bt={s.backtracks} vars={kb.num_primary}+{kb.num_aux} "
                 f"clauses={kb.num_clauses}]")
        if clue:
            self.log(f"      revealed [{clue.owner}] {clue_text(clue)}")
        self.selected = forced.cell
        self.highlight_clue(clue)
        return None

    def on_hint(self) -> None:
        state = self.state()
        if state.is_solved():
            return
        try:
            h = hint(state)
        except ValueError:
            self.log("HINT  knowledge base is INCONSISTENT")
            return
        if h is None:
            self.log("HINT  nothing can be proved right now")
        else:
            self.total_sat_calls += h.sat_calls
            self.selected = h.cell
            self.highlighted = set()
            for clue in state.revealed_clues:
                if clue.id in h.clue_ids:
                    self.highlighted |= set(referenced_cells(clue, state.board))
            self.highlighted |= set(h.proved_cells)
            self.log("HINT  " + h.message(state))
        self.refresh()

    def on_step(self) -> None:
        reason = self._agent_move()
        if reason:
            self.log(f"AGENT stop: {reason}")
        self.refresh()

    def on_auto(self) -> None:
        if self.auto_running:
            self.auto_running = False
            return
        self.auto_running = True
        self._auto_tick()

    def _auto_tick(self) -> None:
        if not self.auto_running:
            return
        reason = self._agent_move()
        self.refresh()
        if reason:
            self.auto_running = False
            self.log(f"AGENT stop: {reason}")
            return
        self.root.after(350, self._auto_tick)


def main(argv: list[str]) -> None:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT_PUZZLE
    root = tk.Tk()
    ManualGUI(root, path)
    root.mainloop()


if __name__ == "__main__":
    main(sys.argv)
