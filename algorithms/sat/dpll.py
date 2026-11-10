"""[B] DPLL SAT solver.

* unit propagation (repeated clause scan)
* conflict detection (a clause with every literal false)
* deterministic variable selection (``heuristics.lowest_index``)
* recursive branching (True first, then False) with backtracking
* returns SAT + complete model over 1..num_vars, or UNSAT
* counts decisions / propagations / backtracks / runtime

``assumptions`` are literals forced before search (e.g. ``[-v]`` to test KB AND NOT C_v).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional, Sequence

from algorithms.sat import cnf, heuristics
from algorithms.sat.stats import SolverStats

Clause = list[int]


class SATStatus(str, Enum):
    SAT = "SAT"
    UNSAT = "UNSAT"


@dataclass
class SolveResult:
    status: SATStatus
    model: Optional[dict[int, bool]] = None  # var -> value, complete over 1..num_vars when SAT
    stats: SolverStats = field(default_factory=SolverStats)

    @property
    def is_sat(self) -> bool:
        return self.status is SATStatus.SAT


class _Conflict(Exception):
    pass


class DPLLSolver:
    def __init__(self, clauses: Iterable[Iterable[int]], num_vars: int | None = None) -> None:
        self.clauses, self._has_empty = cnf.normalize(clauses)
        self.num_vars = max(num_vars or 0, cnf.max_var(self.clauses))
        self.stats = SolverStats()

    # -- propagation -------------------------------------------------------------
    def _propagate(self, assignment: dict[int, bool]) -> None:
        """Apply unit propagation in place; raise ``_Conflict`` on an empty clause."""
        changed = True
        while changed:
            changed = False
            for cl in self.clauses:
                unassigned = None
                n_unassigned = 0
                satisfied = False
                for lit in cl:
                    val = assignment.get(abs(lit))
                    if val is None:
                        n_unassigned += 1
                        unassigned = lit
                    elif val == (lit > 0):
                        satisfied = True
                        break
                if satisfied:
                    continue
                if n_unassigned == 0:
                    self.stats.conflicts += 1
                    raise _Conflict
                if n_unassigned == 1:
                    assignment[abs(unassigned)] = unassigned > 0
                    self.stats.propagations += 1
                    changed = True

    # -- search ------------------------------------------------------------------
    def _search(self, assignment: dict[int, bool]) -> Optional[dict[int, bool]]:
        try:
            self._propagate(assignment)
        except _Conflict:
            return None
        var = heuristics.lowest_index(self.clauses, assignment)
        if var is None:
            return assignment  # every clause satisfied
        for value in (True, False):
            self.stats.decisions += 1
            branch = dict(assignment)
            branch[var] = value
            result = self._search(branch)
            if result is not None:
                return result
            self.stats.backtracks += 1
        return None

    def solve(self, assumptions: Sequence[int] = ()) -> SolveResult:
        self.stats = SolverStats()
        start = time.perf_counter()
        model = None
        if not self._has_empty:
            assignment: dict[int, bool] = {}
            ok = True
            for lit in assumptions:
                v, val = abs(lit), lit > 0
                if assignment.get(v, val) != val:
                    ok = False  # contradictory assumptions
                    break
                assignment[v] = val
            if ok:
                model = self._search(assignment)
        self.stats.runtime = time.perf_counter() - start
        if model is None:
            return SolveResult(SATStatus.UNSAT, None, self.stats)
        full = {v: model.get(v, False) for v in range(1, max(self.num_vars, max(model, default=0)) + 1)}
        return SolveResult(SATStatus.SAT, full, self.stats)


def solve(clauses: Iterable[Iterable[int]], num_vars: int | None = None,
          assumptions: Sequence[int] = ()) -> SolveResult:
    return DPLLSolver(clauses, num_vars).solve(assumptions)
