"""[A] Extension clues (beyond the 6 core templates).

1. ``PARITY``   - the number of criminals (or innocents) in a region is ODD / EVEN.
                  CNF: XOR chain with auxiliary variables (``cardinality.parity``).
2. ``COMPARE``  - region A has MORE / FEWER / EQUAL criminals (or innocents) than region B.
                  CNF: two sequential unary counters (``cardinality.compare``).
3. Advanced region expressions (``corners``, ``edges``, ``between``,
   ``common_neighbors``) usable by every counting clue - see ``regions.py``.

Each extension type provides three functions, wired into the dispatch tables of
``clues.py`` (validation), ``encoder.py`` (CNF) and ``evaluator.py`` (semantics):

* ``validate_*(clue, board) -> list[cell]``     cells referenced (for highlighting)
* ``encode_*(clue, board, var, new_var) -> clauses``
* ``evaluate_*(clue, board, criminal) -> bool`` direct semantics, no CNF
"""

from __future__ import annotations

from typing import Callable, Mapping

from algorithms.logic import cardinality
from algorithms.logic.errors import ClueValidationError
from algorithms.logic.models import Board, Clue, Status, sort_row_major
from algorithms.logic.regions import clue_region

Clause = list[int]
VarOf = Callable[[str], int]   # cell -> primary variable
NewVar = Callable[[], int]     # allocate one auxiliary variable

PARITIES = ("ODD", "EVEN")
COMPARISONS = ("MORE", "FEWER", "EQUAL")


# ------------------------------------------------------------------- shared helpers
def validate_counted_status(clue: Clue) -> Status:
    try:
        return clue.counted_status
    except ValueError:
        raise ClueValidationError(f"{clue.id}: counts must be CRIMINAL or INNOCENT") from None


def counted_literals(clue: Clue, cells: list[str], var: VarOf) -> list[int]:
    """Literals that are true exactly when a cell has the counted status."""
    sign = 1 if clue.counted_status is Status.CRIMINAL else -1
    return [sign * var(c) for c in cells]


def count(clue: Clue, cells: list[str], criminal: Mapping[str, bool]) -> int:
    want = clue.counted_status is Status.CRIMINAL
    return sum(1 for c in cells if criminal[c] == want)


# ------------------------------------------------------------------------- PARITY
def validate_parity(clue: Clue, board: Board) -> list[str]:
    cells = clue_region(clue, board)
    validate_counted_status(clue)
    parity = clue.params.get("parity")
    if parity not in PARITIES:
        raise ClueValidationError(f"{clue.id}: parity must be one of {PARITIES}, got {parity!r}")
    if not cells and parity == "ODD":
        raise ClueValidationError(f"{clue.id}: an empty region cannot hold an odd count")
    return cells


def encode_parity(clue: Clue, board: Board, var: VarOf, new_var: NewVar) -> list[Clause]:
    lits = counted_literals(clue, clue_region(clue, board), var)
    return cardinality.parity(lits, clue.params["parity"] == "ODD", new_var)


def evaluate_parity(clue: Clue, board: Board, criminal: Mapping[str, bool]) -> bool:
    n = count(clue, clue_region(clue, board), criminal)
    return n % 2 == (1 if clue.params["parity"] == "ODD" else 0)


# ------------------------------------------------------------------------ COMPARE
def validate_compare(clue: Clue, board: Board) -> list[str]:
    a = clue_region(clue, board, "region_a")
    b = clue_region(clue, board, "region_b")
    validate_counted_status(clue)
    op = clue.params.get("op")
    if op not in COMPARISONS:
        raise ClueValidationError(f"{clue.id}: op must be one of {COMPARISONS}, got {op!r}")
    if set(a) == set(b):
        raise ClueValidationError(f"{clue.id}: region_a and region_b are the same region")
    return sort_row_major(set(a) | set(b))


def encode_compare(clue: Clue, board: Board, var: VarOf, new_var: NewVar) -> list[Clause]:
    a = counted_literals(clue, clue_region(clue, board, "region_a"), var)
    b = counted_literals(clue, clue_region(clue, board, "region_b"), var)
    return cardinality.compare(a, b, clue.params["op"], new_var)


def evaluate_compare(clue: Clue, board: Board, criminal: Mapping[str, bool]) -> bool:
    na = count(clue, clue_region(clue, board, "region_a"), criminal)
    nb = count(clue, clue_region(clue, board, "region_b"), criminal)
    op = clue.params["op"]
    return na > nb if op == "MORE" else na < nb if op == "FEWER" else na == nb
