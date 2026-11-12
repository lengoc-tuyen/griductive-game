"""[C] Deduction loop.

    repeat:
        KB_t <- build_kb(public state)          (revealed clues + proved verdicts only)
        if KB_t UNSAT                     -> INCONSISTENT
        pick first forced cell, row-major  (never guess)
        if none                           -> STUCK
        submit verdict to the engine, receive the revealed clue
    until solved

Every step is recorded in a ``DeductionTrace`` (active clues, SAT queries, verdict,
revealed clue); totals for the experiments are kept in ``AgentRun``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from algorithms.agent.entailment import classify
from algorithms.agent.knowledge_base import KnowledgeBase, build_kb
from algorithms.agent.public_state import EngineProtocol, PublicState, VerdictResult
from algorithms.agent.trace import DeductionTrace, TraceStep
from algorithms.logic.models import Status
from algorithms.sat.dpll import SolverTimeout
from algorithms.sat.stats import SolverStats


class AgentOutcome(str, Enum):
    SOLVED = "SOLVED"
    STUCK = "STUCK"                # no forced verdict, puzzle not finished
    INCONSISTENT = "INCONSISTENT"  # KB unsatisfiable
    REJECTED = "REJECTED"          # engine refused a verdict the agent proved (bug / bad puzzle)
    STEP_LIMIT = "STEP_LIMIT"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True)
class ForcedVerdict:
    cell: str
    status: Status


@dataclass
class AgentRun:
    outcome: AgentOutcome
    trace: DeductionTrace = field(default_factory=DeductionTrace)
    stats: SolverStats = field(default_factory=SolverStats)  # summed over every SAT call
    sat_calls: int = 0
    max_primary_vars: int = 0
    max_aux_vars: int = 0
    max_clauses: int = 0
    runtime: float = 0.0  # wall-clock seconds for the whole run

    @property
    def steps(self) -> list[TraceStep]:
        return self.trace.steps

    def _absorb(self, kb: KnowledgeBase) -> None:
        self.sat_calls += kb.sat_calls
        self.stats.merge(kb.stats)
        self.max_primary_vars = max(self.max_primary_vars, kb.num_primary)
        self.max_aux_vars = max(self.max_aux_vars, kb.num_aux)
        self.max_clauses = max(self.max_clauses, kb.num_clauses)

    def summary(self) -> dict[str, object]:
        """Flat metrics for the experiments table (section 4.5)."""
        return {
            "outcome": self.outcome.value,
            "steps": len(self.steps),
            "primary_vars": self.max_primary_vars,
            "aux_vars": self.max_aux_vars,
            "clauses": self.max_clauses,
            "sat_calls": self.sat_calls,
            "decisions": self.stats.decisions,
            "propagations": self.stats.propagations,
            "backtracks": self.stats.backtracks,
            "conflicts": self.stats.conflicts,
            "sat_runtime": self.stats.runtime,
            "runtime": self.runtime,
        }


def find_forced(kb: KnowledgeBase) -> Optional[ForcedVerdict]:
    """First unresolved cell (row-major) whose status is entailed by ``kb``.

    Raises ``ValueError`` if the KB is inconsistent.
    """
    if not kb.is_consistent():
        raise ValueError("knowledge base is inconsistent")
    for cell in kb.state.unresolved_cells():
        status = classify(kb, cell).status
        if status is not None:
            return ForcedVerdict(cell, status)
    return None


def next_forced(state: PublicState) -> Optional[ForcedVerdict]:
    return find_forced(build_kb(state))


class DeductionAgent:
    def __init__(self, max_steps: int | None = None, time_limit: float | None = None) -> None:
        self.max_steps = max_steps
        self.time_limit = time_limit  # seconds for the whole run

    def run(self, engine: EngineProtocol) -> AgentRun:
        start = time.perf_counter()
        deadline = None if self.time_limit is None else start + self.time_limit
        run = AgentRun(outcome=AgentOutcome.STUCK)
        try:
            run.outcome = self._loop(engine, run, deadline)
        finally:
            run.runtime = time.perf_counter() - start
            run.trace.outcome = run.outcome.value
        return run

    def _loop(self, engine: EngineProtocol, run: AgentRun, deadline: Optional[float]) -> AgentOutcome:
        while True:
            state = engine.public_state()
            if state.is_solved():
                return AgentOutcome.SOLVED
            if self.max_steps is not None and len(run.steps) >= self.max_steps:
                return AgentOutcome.STEP_LIMIT

            kb = build_kb(state, deadline)
            try:
                forced = find_forced(kb)
            except ValueError:
                return self._stop(run, kb, AgentOutcome.INCONSISTENT)
            except SolverTimeout as e:
                kb.stats.merge(e.stats)
                return self._stop(run, kb, AgentOutcome.TIMEOUT)
            if forced is None:
                return self._stop(run, kb, AgentOutcome.STUCK)
            run._absorb(kb)

            result, clue = engine.submit(forced.cell, forced.status)
            if result is not VerdictResult.ACCEPTED:
                return AgentOutcome.REJECTED
            run.trace.steps.append(TraceStep(
                index=len(run.steps) + 1,
                cell=forced.cell,
                verdict=forced.status,
                active_clue_ids=state.clue_ids(),
                queries=list(kb.queries),
                num_primary=kb.num_primary,
                num_aux=kb.num_aux,
                num_clauses=kb.num_clauses,
                revealed_clue=clue,
            ))

    @staticmethod
    def _stop(run: AgentRun, kb: KnowledgeBase, outcome: AgentOutcome) -> AgentOutcome:
        run._absorb(kb)
        run.trace.final_queries = list(kb.queries)
        return outcome
