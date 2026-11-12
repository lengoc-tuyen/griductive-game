"""[A] Clue validation (core templates + extensions).

``validate(clue, board)`` raises ``ClueValidationError`` when parameters are wrong
(unknown person, bad status, region error, k outside [0, |R|], ...).
``referenced_cells(clue, board)`` returns the cells a clue talks about - the GUI can
use it to highlight a selected clue.
"""

from __future__ import annotations

from typing import Callable

from algorithms.logic import extensions
from algorithms.logic.errors import ClueValidationError
from algorithms.logic.models import COUNTING_TYPES, Board, Clue, ClueType, Status
from algorithms.logic.regions import clue_region

__all__ = ["ClueValidationError", "validate", "referenced_cells", "is_counting"]


def _person_cell(clue: Clue, key: str, board: Board) -> str:
    name = clue.params.get(key)
    if not isinstance(name, str):
        raise ClueValidationError(f"{clue.id}: param {key!r} must be a person name")
    try:
        return board.cell_of(name)
    except KeyError as e:
        raise ClueValidationError(f"{clue.id}: {e}") from None


def _validate_fact(clue: Clue, board: Board) -> list[str]:
    cell = _person_cell(clue, "person", board)
    try:
        Status(clue.params.get("status"))
    except ValueError:
        raise ClueValidationError(f"{clue.id}: status must be CRIMINAL or INNOCENT") from None
    return [cell]


def _validate_pair(clue: Clue, board: Board) -> list[str]:
    a = _person_cell(clue, "a", board)
    b = _person_cell(clue, "b", board)
    if a == b:
        raise ClueValidationError(f"{clue.id}: {clue.type.value} needs two different people")
    return [a, b]


def _validate_counting(clue: Clue, board: Board) -> list[str]:
    cells = clue_region(clue, board)
    extensions.validate_counted_status(clue)
    k = clue.params.get("k")
    if not isinstance(k, int) or isinstance(k, bool) or not (0 <= k <= len(cells)):
        raise ClueValidationError(f"{clue.id}: k must be an int in [0, {len(cells)}], got {k!r}")
    return cells


_VALIDATORS: dict[ClueType, Callable[[Clue, Board], list[str]]] = {
    ClueType.FACT: _validate_fact,
    ClueType.SAME: _validate_pair,
    ClueType.DIFFERENT: _validate_pair,
    ClueType.EXACTLY: _validate_counting,
    ClueType.AT_LEAST: _validate_counting,
    ClueType.AT_MOST: _validate_counting,
    ClueType.PARITY: extensions.validate_parity,
    ClueType.COMPARE: extensions.validate_compare,
}


def validate(clue: Clue, board: Board) -> None:
    referenced_cells(clue, board)


def referenced_cells(clue: Clue, board: Board) -> list[str]:
    """Validate ``clue`` and return the cells it refers to / counts over."""
    if not board.has_cell(clue.owner):
        raise ClueValidationError(f"{clue.id}: owner {clue.owner!r} is not on the board")
    validator = _VALIDATORS.get(clue.type)
    if validator is None:
        raise ClueValidationError(f"{clue.id}: unsupported clue type {clue.type!r}")
    return validator(clue, board)


def is_counting(clue: Clue) -> bool:
    return clue.type in COUNTING_TYPES
