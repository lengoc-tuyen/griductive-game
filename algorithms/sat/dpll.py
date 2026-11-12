"""[B] DPLL SAT solver.

* unit propagation with two watched literals (no clause scanning on each assignment)
* conflict detection (a clause whose literals are all false)
* deterministic variable selection (a static order from ``heuristics``)
* recursive branching (True first, then False) with chronological backtracking,
  undone through an assignment trail instead of copying the assignment
* returns SAT + a complete model over 1..num_vars, or UNSAT
* records decisions / propagations / backtracks / conflicts / runtime per call

``assumptions`` are literals fixed before search (e.g. ``[-v]`` to test KB AND NOT C_v);
the clause database is never modified by them, so one solver answers many queries.
``add_clause`` adds a permanent clause between calls (used for model blocking).
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Optional, Sequence

from algorithms.sat import cnf, heuristics
from algorithms.sat.stats import SolverStats

Clause = list[int]

_UNASSIGNED, _TRUE, _FALSE = 0, 1, -1


class SATStatus(str, Enum):
    SAT = "SAT"
    UNSAT = "UNSAT"


class SolverTimeout(RuntimeError):
    """Raised when ``time_limit`` / ``max_decisions`` is exceeded; carries the partial stats."""

    def __init__(self, stats: SolverStats) -> None:
        super().__init__(f"SAT solver limit exceeded after {stats.decisions} decisions")
        self.stats = stats


@dataclass
class SolveResult:
    status: SATStatus
    model: Optional[dict[int, bool]] = None  # var -> value, complete over 1..num_vars when SAT
    stats: SolverStats = field(default_factory=SolverStats)

    @property
    def is_sat(self) -> bool:
        return self.status is SATStatus.SAT


class DPLLSolver:
    def __init__(self, clauses: Iterable[Iterable[int]], num_vars: int | None = None,
                 heuristic: str = "lowest_index") -> None:
        clauses, self._has_empty = cnf.normalize(clauses)
        self.num_vars = max(num_vars or 0, cnf.max_var(clauses))
        self._order_fn = heuristics.get(heuristic)
        self.clauses: list[Clause] = []
        self._units: list[int] = []
        self._watches: list[list[int]] = [[] for _ in range(2 * self.num_vars + 2)]
        for cl in clauses:
            self._attach(cl)
        self._order = self._order_fn(self.clauses + [[u] for u in self._units])
        self.stats = SolverStats()

    # -- clause database -----------------------------------------------------------
    def _widx(self, lit: int) -> int:
        return 2 * lit if lit > 0 else -2 * lit + 1

    def _attach(self, cl: Clause) -> None:
        if not cl:
            self._has_empty = True
        elif len(cl) == 1:
            self._units.append(cl[0])
        else:
            idx = len(self.clauses)
            self.clauses.append(list(cl))
            self._watches[self._widx(cl[0])].append(idx)
            self._watches[self._widx(cl[1])].append(idx)

    def add_clause(self, clause: Iterable[int]) -> None:
        """Add a permanent clause over existing variables (call between ``solve``s)."""
        normalized, _ = cnf.normalize([clause])
        if not normalized:
            return  # tautology
        cl = normalized[0]
        if any(abs(lit) > self.num_vars for lit in cl):
            raise ValueError("add_clause: unknown variable")
        self._attach(cl)
        known = set(self._order)
        self._order += sorted({abs(lit) for lit in cl} - known)

    # -- assignment ------------------------------------------------------------------
    def _value(self, lit: int) -> int:
        v = self._val[abs(lit)]
        return v if lit > 0 else -v

    def _assign(self, lit: int) -> None:
        self._val[abs(lit)] = _TRUE if lit > 0 else _FALSE
        self._trail.append(lit)

    def _undo(self, mark: int) -> None:
        trail, val = self._trail, self._val
        while len(trail) > mark:
            val[abs(trail.pop())] = _UNASSIGNED
        self._qhead = mark

    def _propagate(self) -> bool:
        """Unit propagation over the watched literals. Returns False on a conflict."""
        trail, val, watches, clauses = self._trail, self._val, self._watches, self.clauses
        while self._qhead < len(trail):
            false_lit = -trail[self._qhead]
            self._qhead += 1
            wl = watches[self._widx(false_lit)]
            i = 0
            while i < len(wl):
                cl = clauses[wl[i]]
                if cl[0] == false_lit:  # keep the falsified watch in position 1
                    cl[0], cl[1] = cl[1], cl[0]
                first = cl[0]
                if self._value(first) == _TRUE:
                    i += 1
                    continue
                for k in range(2, len(cl)):  # look for a replacement watch
                    if self._value(cl[k]) != _FALSE:
                        cl[1], cl[k] = cl[k], cl[1]
                        watches[self._widx(cl[1])].append(wl[i])
                        wl[i] = wl[-1]
                        wl.pop()
                        break
                else:
                    if self._value(first) == _FALSE:
                        self.stats.conflicts += 1
                        return False
                    self._assign(first)  # unit clause
                    self.stats.propagations += 1
                    i += 1
        return True

    # -- search ------------------------------------------------------------------------
    def _pick(self) -> Optional[int]:
        order, val = self._order, self._val
        while self._pos < len(order) and val[order[self._pos]] != _UNASSIGNED:
            self._pos += 1
        return order[self._pos] if self._pos < len(order) else None

    def _check_limits(self) -> None:
        if self._max_decisions is not None and self.stats.decisions > self._max_decisions:
            raise SolverTimeout(self.stats)
        if self._deadline is not None and time.perf_counter() > self._deadline:
            raise SolverTimeout(self.stats)

    def _search(self) -> bool:
        if not self._propagate():
            return False
        pos = self._pos
        var = self._pick()
        if var is None:
            return True  # every variable assigned without conflict
        mark = len(self._trail)
        for lit in (var, -var):
            self.stats.decisions += 1
            self._check_limits()
            self._assign(lit)
            if self._search():
                return True
            self._undo(mark)
            self._pos = pos
            self.stats.backtracks += 1
        return False

    def solve(self, assumptions: Sequence[int] = (), *, time_limit: float | None = None,
              max_decisions: int | None = None) -> SolveResult:
        self.stats = SolverStats()
        self._val = [_UNASSIGNED] * (self.num_vars + 1)
        self._trail: list[int] = []
        self._qhead = 0
        self._pos = 0
        self._max_decisions = max_decisions
        start = time.perf_counter()
        self._deadline = None if time_limit is None else start + time_limit

        if self.num_vars + 100 > sys.getrecursionlimit():  # recursion depth <= #decisions
            sys.setrecursionlimit(self.num_vars + 100)
        try:
            sat = not self._has_empty and self._load(assumptions) and self._search()
        finally:
            self.stats.runtime = time.perf_counter() - start
        if not sat:
            return SolveResult(SATStatus.UNSAT, None, self.stats)
        model = {v: self._val[v] == _TRUE for v in range(1, self.num_vars + 1)}
        return SolveResult(SATStatus.SAT, model, self.stats)

    def _load(self, assumptions: Sequence[int]) -> bool:
        """Assign assumptions (not counted) and unit clauses (counted as propagations)."""
        outside: set[int] = set()  # assumptions on variables the formula never mentions
        for lit in assumptions:
            if lit == 0:
                raise ValueError("literal 0 is not allowed")
            if abs(lit) > self.num_vars:
                if -lit in outside:
                    return False
                outside.add(lit)
                continue
            value = self._value(lit)
            if value == _FALSE:
                return False
            if value == _UNASSIGNED:
                self._assign(lit)
        for lit in self._units:
            value = self._value(lit)
            if value == _FALSE:
                self.stats.conflicts += 1
                return False
            if value == _UNASSIGNED:
                self._assign(lit)
                self.stats.propagations += 1
        return True


def solve(clauses: Iterable[Iterable[int]], num_vars: int | None = None,
          assumptions: Sequence[int] = (), heuristic: str = "lowest_index") -> SolveResult:
    return DPLLSolver(clauses, num_vars, heuristic).solve(assumptions)
