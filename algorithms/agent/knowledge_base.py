"""[C] Knowledge base KB_t = CNF(revealed clues) AND unit clauses for proved verdicts.

Built ONLY from a ``PublicState`` - hidden statuses and unrevealed clues never enter.
Every SAT query goes through ``KnowledgeBase.query`` so calls and stats are counted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from algorithms.agent.public_state import PublicState
from algorithms.logic.encoder import CNFEncoder, EncodedCNF
from algorithms.logic.variable_map import VariableMap
from algorithms.sat.dpll import DPLLSolver, SolveResult
from algorithms.sat.stats import SolverStats


@dataclass
class KnowledgeBase:
    state: PublicState
    var_map: VariableMap
    cnf: EncodedCNF
    stats: SolverStats = field(default_factory=SolverStats)  # summed over all queries
    sat_calls: int = 0
    queries: list[tuple[tuple[int, ...], bool]] = field(default_factory=list)  # (assumptions, sat?)
    _solver: DPLLSolver | None = field(default=None, repr=False)
    _consistent: bool | None = field(default=None, repr=False)

    def query(self, assumptions: Sequence[int] = ()) -> SolveResult:
        if self._solver is None:
            self._solver = DPLLSolver(self.cnf.clauses, self.cnf.num_vars)
        result = self._solver.solve(assumptions)
        self.sat_calls += 1
        self.stats.merge(result.stats)
        self.queries.append((tuple(assumptions), result.is_sat))
        return result

    def is_consistent(self) -> bool:
        if self._consistent is None:
            self._consistent = self.query().is_sat
        return self._consistent

    @property
    def num_primary(self) -> int:
        return self.cnf.num_primary

    @property
    def num_aux(self) -> int:
        return self.cnf.num_aux

    @property
    def num_clauses(self) -> int:
        return self.cnf.num_clauses


def build_kb(state: PublicState) -> KnowledgeBase:
    var_map = VariableMap(state.board)
    encoder = CNFEncoder(state.board, var_map)
    encoded = encoder.encode(state.revealed_clues, state.proved)
    return KnowledgeBase(state=state, var_map=var_map, cnf=encoded)
