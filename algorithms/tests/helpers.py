"""Test helpers: fixture loading + a minimal FakeEngine implementing EngineProtocol.

This is NOT the real GameEngine (that lives in ``frontend/engine``, owned by D);
it only exists so the agent can be tested end-to-end inside ``algorithms``.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Optional

from algorithms.agent.entailment import check_verdict
from algorithms.agent.public_state import PublicState, VerdictResult
from algorithms.logic.models import Board, Clue, Status

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


class FakeEngine:
    def __init__(self, puzzle: dict) -> None:
        self.board = Board.from_dict(puzzle)
        self._solution = {c: Status(s) for c, s in puzzle["solution"].items()}
        self._clue_of = {}
        for d in puzzle["clues"]:
            clue = Clue.from_dict(d)
            self._clue_of[clue.owner] = clue
        self._initial = list(puzzle.get("initially_revealed", []))
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
        assert self._solution[cell] is Status(status), "proved verdict disagrees with solution"
        self._proved[cell] = Status(status)
        clue = self._clue_of.get(cell)
        if clue is not None:
            self._revealed.append(clue)
        return result, clue


def brute_force_models(clauses: list[list[int]], num_vars: int):
    """Yield every satisfying assignment (as dict var->bool). Only for tiny formulas."""
    for bits in itertools.product((False, True), repeat=num_vars):
        a = {i + 1: b for i, b in enumerate(bits)}
        if all(any(a[abs(l)] == (l > 0) for l in cl) for cl in clauses):
            yield a
