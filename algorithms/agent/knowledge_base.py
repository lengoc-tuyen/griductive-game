"""[C] Knowledge base KB_t = CNF(revealed clues) AND unit clauses for proved verdicts.

Built ONLY from a ``PublicState`` - hidden statuses and unrevealed clues never enter.
Every SAT query goes through ``KnowledgeBase.query`` so calls and stats are counted
and logged for the deduction trace.

Every satisfying model found is remembered as a *witness*: if some model has
C_i = True and another has C_i = False, character i is certainly UNKNOWN and no
further query about it is needed (see ``entailment.classify``).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Sequence

from algorithms.agent.public_state import PublicState
from algorithms.agent.trace import SatQuery
from algorithms.logic.encoder import CNFEncoder, EncodedCNF
from algorithms.logic.variable_map import VariableMap
from algorithms.sat.dpll import DPLLSolver, SolveResult
from algorithms.sat.stats import SolverStats


@dataclass
class KnowledgeBase:
    state: PublicState
    var_map: VariableMap
    cnf: EncodedCNF
    deadline: Optional[float] = None  # time.perf_counter() value; queries raise SolverTimeout after it
    stats: SolverStats = field(default_factory=SolverStats)  # summed over all queries
    queries: list[SatQuery] = field(default_factory=list)
    _solver: Optional[DPLLSolver] = field(default=None, repr=False)
    _consistent: Optional[bool] = field(default=None, repr=False)
    _seen: dict[str, set[bool]] = field(default_factory=dict, repr=False)  # cell -> values in some model

    # -- queries -------------------------------------------------------------------
    def query(self, assumptions: Sequence[int] = ()) -> SolveResult:
        if self._solver is None:
            self._solver = DPLLSolver(self.cnf.clauses, self.cnf.num_vars)
        limit = None if self.deadline is None else max(0.0, self.deadline - time.perf_counter())
        result = self._solver.solve(assumptions, time_limit=limit)
        self.stats.merge(result.stats)
        self.queries.append(SatQuery(tuple(assumptions), self.describe(assumptions),
                                     result.is_sat, result.stats))
        if result.is_sat:
            for cell in self.state.board.cells():
                self._seen.setdefault(cell, set()).add(result.model[self.var_map.var(cell)])
        return result

    def is_consistent(self) -> bool:
        if self._consistent is None:
            self._consistent = self.query().is_sat
        return self._consistent

    def witnessed(self, cell: str) -> set[bool]:
        """Values of C_cell (True = criminal) seen in some model found so far."""
        return self._seen.get(cell, set())

    # -- reporting -----------------------------------------------------------------
    def literal_name(self, lit: int) -> str:
        v = abs(lit)
        name = f"C[{self.var_map.cell(v)}]" if self.var_map.is_primary(v) else f"aux{v}"
        return name if lit > 0 else f"NOT {name}"

    def describe(self, assumptions: Sequence[int]) -> str:
        return " AND ".join(["KB"] + [self.literal_name(l) for l in assumptions])

    @property
    def sat_calls(self) -> int:
        return len(self.queries)

    @property
    def num_primary(self) -> int:
        return self.cnf.num_primary

    @property
    def num_aux(self) -> int:
        return self.cnf.num_aux

    @property
    def num_clauses(self) -> int:
        return self.cnf.num_clauses


def build_kb(state: PublicState, deadline: Optional[float] = None) -> KnowledgeBase:
    var_map = VariableMap(state.board)
    encoder = CNFEncoder(state.board, var_map)
    encoded = encoder.encode(state.revealed_clues, state.proved)
    return KnowledgeBase(state=state, var_map=var_map, cnf=encoded, deadline=deadline)
