"""[C] Uniqueness check on the complete clue set.

Separate from the deduction loop (it may read every clue - it is a puzzle-authoring /
verification tool, not something the playing agent uses):

    KB_full = CNF(all clues) AND unit clauses for the initially known statuses
    repeat: find a model, record its primary assignment, add a clause blocking it
    until UNSAT or ``max_solutions`` models were found

Blocking clauses only mention primary variables C_i, so two models that differ
only in auxiliary variables count as the same solution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping, Optional

from algorithms.logic.encoder import CNFEncoder
from algorithms.logic.models import Board, Clue, Status
from algorithms.sat.dpll import DPLLSolver
from algorithms.sat.stats import SolverStats


class Uniqueness(str, Enum):
    UNIQUE = "UNIQUE"
    MULTIPLE = "MULTIPLE"
    NO_SOLUTION = "NO_SOLUTION"


@dataclass
class UniquenessResult:
    status: Uniqueness
    solutions: list[dict[str, Status]]  # at most ``max_solutions`` (cell -> status)
    sat_calls: int
    num_primary: int
    num_aux: int
    num_clauses: int
    stats: SolverStats = field(default_factory=SolverStats)

    @property
    def is_unique(self) -> bool:
        return self.status is Uniqueness.UNIQUE


def enumerate_solutions(board: Board, clues: Iterable[Clue], known: Optional[Mapping[str, Status]] = None,
                        max_solutions: int = 2) -> UniquenessResult:
    encoder = CNFEncoder(board)
    encoded = encoder.encode(clues, known)
    solver = DPLLSolver(encoded.clauses, encoded.num_vars)
    cells = board.cells()
    stats = SolverStats()
    solutions: list[dict[str, Status]] = []
    sat_calls = 0
    while len(solutions) < max_solutions:
        result = solver.solve()
        sat_calls += 1
        stats.merge(result.stats)
        if not result.is_sat:
            break
        values = {c: result.model[encoder.vars.var(c)] for c in cells}
        solutions.append({c: Status.CRIMINAL if val else Status.INNOCENT for c, val in values.items()})
        solver.add_clause([-encoder.vars.var(c) if val else encoder.vars.var(c) for c, val in values.items()])

    status = (Uniqueness.NO_SOLUTION if not solutions
              else Uniqueness.UNIQUE if len(solutions) == 1 else Uniqueness.MULTIPLE)
    return UniquenessResult(status, solutions, sat_calls, encoded.num_primary, encoded.num_aux,
                            encoded.num_clauses, stats)


def check_uniqueness(board: Board, clues: Iterable[Clue],
                     known: Optional[Mapping[str, Status]] = None) -> UniquenessResult:
    """UNIQUE iff the full clue set (plus ``known`` statuses) has exactly one solution."""
    return enumerate_solutions(board, clues, known, max_solutions=2)
