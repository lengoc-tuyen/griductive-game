"""[C] Deduction loop (basic version).

    repeat:
        KB_t <- build_kb(public state)
        if KB_t UNSAT                     -> INCONSISTENT
        pick first forced cell, row-major  (never guess)
        if none                           -> STUCK
        submit verdict to the engine, receive the revealed clue
    until solved

Each step records a small trace entry; the full trace (SAT queries etc.) is an
extension planned in ``trace.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from algorithms.agent.entailment import Classification, classify
from algorithms.agent.knowledge_base import KnowledgeBase, build_kb
from algorithms.agent.public_state import EngineProtocol, PublicState, VerdictResult
from algorithms.logic.models import Status
from algorithms.sat.stats import SolverStats


class AgentOutcome(str, Enum):
    SOLVED = "SOLVED"
    STUCK = "STUCK"                # no forced verdict, puzzle not finished
    INCONSISTENT = "INCONSISTENT"  # KB unsatisfiable
    REJECTED = "REJECTED"          # engine refused a verdict the agent proved (bug / bad puzzle)
    STEP_LIMIT = "STEP_LIMIT"


@dataclass(frozen=True)
class ForcedVerdict:
    cell: str
    status: Status


@dataclass
class Step:
    index: int
    cell: str
    verdict: Status
    active_clue_ids: list[str]
    sat_calls: int
    revealed_clue_id: Optional[str]


@dataclass
class AgentRun:
    outcome: AgentOutcome
    steps: list[Step] = field(default_factory=list)
    sat_calls: int = 0
    stats: SolverStats = field(default_factory=SolverStats)
    max_primary_vars: int = 0
    max_aux_vars: int = 0
    max_clauses: int = 0


def find_forced(kb: KnowledgeBase) -> Optional[ForcedVerdict]:
    """First unresolved cell (row-major) whose status is entailed by ``kb``.

    Raises ``ValueError`` if the KB is inconsistent.
    """
    if not kb.is_consistent():
        raise ValueError("knowledge base is inconsistent")
    for cell in kb.state.unresolved_cells():
        c = classify(kb, cell)
        if c.status is not None:
            return ForcedVerdict(cell, c.status)
    return None


def next_forced(state: PublicState) -> Optional[ForcedVerdict]:
    return find_forced(build_kb(state))


class DeductionAgent:
    def __init__(self, max_steps: int | None = None) -> None:
        self.max_steps = max_steps

    def run(self, engine: EngineProtocol) -> AgentRun:
        run = AgentRun(outcome=AgentOutcome.STUCK)
        while True:
            state = engine.public_state()
            if state.is_solved():
                run.outcome = AgentOutcome.SOLVED
                return run
            if self.max_steps is not None and len(run.steps) >= self.max_steps:
                run.outcome = AgentOutcome.STEP_LIMIT
                return run

            kb = build_kb(state)
            run.max_primary_vars = max(run.max_primary_vars, kb.num_primary)
            run.max_aux_vars = max(run.max_aux_vars, kb.num_aux)
            run.max_clauses = max(run.max_clauses, kb.num_clauses)
            try:
                forced = find_forced(kb)
            except ValueError:
                forced = None
                run.outcome = AgentOutcome.INCONSISTENT
            finally:
                run.sat_calls += kb.sat_calls
                run.stats.merge(kb.stats)

            if run.outcome is AgentOutcome.INCONSISTENT:
                return run
            if forced is None:
                run.outcome = AgentOutcome.STUCK
                return run

            result, clue = engine.submit(forced.cell, forced.status)
            if result is not VerdictResult.ACCEPTED:
                run.outcome = AgentOutcome.REJECTED
                return run
            run.steps.append(Step(
                index=len(run.steps) + 1,
                cell=forced.cell,
                verdict=forced.status,
                active_clue_ids=state.clue_ids(),
                sat_calls=kb.sat_calls,
                revealed_clue_id=clue.id if clue is not None else None,
            ))
