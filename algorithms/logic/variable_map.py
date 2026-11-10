"""[A] Deterministic mapping character/cell -> propositional variable.

Primary variables ``C_i`` (True = Criminal) get ids 1..n*n in row-major order of
their cells. Auxiliary variables (used by some encodings) are allocated after
that range, so the two are always separate.
"""

from __future__ import annotations

from algorithms.logic.models import Board


class VariableMap:
    def __init__(self, board: Board) -> None:
        self.board = board
        self._cell_to_var: dict[str, int] = {}
        self._var_to_cell: dict[int, str] = {}
        for i, cell in enumerate(board.cells(), start=1):
            self._cell_to_var[cell] = i
            self._var_to_cell[i] = cell
        self.num_primary = len(self._cell_to_var)
        self._next_aux = self.num_primary + 1

    def var(self, cell: str) -> int:
        return self._cell_to_var[cell]

    def var_of_name(self, name: str) -> int:
        return self._cell_to_var[self.board.cell_of(name)]

    def cell(self, var: int) -> str:
        return self._var_to_cell[var]

    def is_primary(self, var: int) -> bool:
        return 1 <= abs(var) <= self.num_primary

    def new_aux(self) -> int:
        v = self._next_aux
        self._next_aux += 1
        return v

    @property
    def num_aux(self) -> int:
        return self._next_aux - self.num_primary - 1

    @property
    def num_vars(self) -> int:
        return self._next_aux - 1
