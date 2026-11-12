"""[A] Direct semantic evaluator: given a complete assignment, is the clue true?

Works straight from the clue's meaning (counting statuses in regions) and never
calls the CNF encoder, so it can be used to cross-check it
(``tests/test_encoder_vs_evaluator.py``) and to verify puzzle solutions.

An assignment maps every cell to a ``Status`` or to a bool (True = CRIMINAL).
"""

from __future__ import annotations

from typing import Callable, Iterable, Mapping, Union

from algorithms.logic import clues as clue_rules
from algorithms.logic import extensions
from algorithms.logic.models import Board, Clue, ClueType, Status
from algorithms.logic.regions import clue_region

Assignment = Mapping[str, Union[Status, bool]]


def _as_bools(assignment: Assignment, board: Board) -> dict[str, bool]:
    out = {}
    for cell in board.cells():
        if cell not in assignment:
            raise ValueError(f"assignment is missing cell {cell}")
        value = assignment[cell]
        out[cell] = value if isinstance(value, bool) else Status(value) is Status.CRIMINAL
    return out


def _fact(clue: Clue, board: Board, criminal: Mapping[str, bool]) -> bool:
    return criminal[board.cell_of(clue.params["person"])] == (Status(clue.params["status"]) is Status.CRIMINAL)


def _same(clue: Clue, board: Board, criminal: Mapping[str, bool]) -> bool:
    return criminal[board.cell_of(clue.params["a"])] == criminal[board.cell_of(clue.params["b"])]


def _different(clue: Clue, board: Board, criminal: Mapping[str, bool]) -> bool:
    return not _same(clue, board, criminal)


def _counting(compare: Callable[[int, int], bool]):
    def evaluate(clue: Clue, board: Board, criminal: Mapping[str, bool]) -> bool:
        return compare(extensions.count(clue, clue_region(clue, board), criminal), clue.params["k"])

    return evaluate


_EVALUATORS = {
    ClueType.FACT: _fact,
    ClueType.SAME: _same,
    ClueType.DIFFERENT: _different,
    ClueType.EXACTLY: _counting(lambda n, k: n == k),
    ClueType.AT_LEAST: _counting(lambda n, k: n >= k),
    ClueType.AT_MOST: _counting(lambda n, k: n <= k),
    ClueType.PARITY: extensions.evaluate_parity,
    ClueType.COMPARE: extensions.evaluate_compare,
}


def evaluate(clue: Clue, board: Board, assignment: Assignment) -> bool:
    """True iff ``clue`` holds under the complete ``assignment``."""
    clue_rules.validate(clue, board)
    return _EVALUATORS[clue.type](clue, board, _as_bools(assignment, board))


def violated(clues: Iterable[Clue], board: Board, assignment: Assignment) -> list[str]:
    """Ids of the clues that are false under ``assignment`` (empty list = all hold)."""
    return [clue.id for clue in clues if not evaluate(clue, board, assignment)]
