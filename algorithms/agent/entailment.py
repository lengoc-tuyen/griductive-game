"""[C] Entailment classification.

    KB |= C_i      <=>  KB AND NOT C_i is UNSAT   -> CRIMINAL
    KB |= NOT C_i  <=>  KB AND C_i     is UNSAT   -> INNOCENT
    both SAT                                      -> UNKNOWN
    KB itself UNSAT                               -> INCONSISTENT

Optimisation (same answers, fewer SAT calls): the consistency check already returns a
model M of KB, and every later SAT answer returns another model. If M has C_i = True,
then ``KB AND C_i`` is known to be SAT, so only ``KB AND NOT C_i`` has to be asked; and if
the models seen so far contain both values of C_i, i is UNKNOWN without any query.
"""

from __future__ import annotations

from enum import Enum

from algorithms.agent.knowledge_base import KnowledgeBase, build_kb
from algorithms.agent.public_state import PublicState, VerdictResult
from algorithms.logic.models import Status


class Classification(str, Enum):
    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"
    UNKNOWN = "UNKNOWN"
    INCONSISTENT = "INCONSISTENT"

    @property
    def status(self) -> Status | None:
        if self is Classification.CRIMINAL:
            return Status.CRIMINAL
        if self is Classification.INNOCENT:
            return Status.INNOCENT
        return None

    @classmethod
    def of(cls, status: Status) -> "Classification":
        return cls.CRIMINAL if Status(status) is Status.CRIMINAL else cls.INNOCENT


def classify(kb: KnowledgeBase, cell: str) -> Classification:
    if not kb.is_consistent():
        return Classification.INCONSISTENT
    if cell in kb.state.proved:
        return Classification.of(kb.state.proved[cell])
    seen = kb.witnessed(cell)
    if len(seen) == 2:
        return Classification.UNKNOWN
    criminal_possible = True in seen        # exactly one value is witnessed here
    v = kb.var_map.var(cell)
    if not kb.query([-v] if criminal_possible else [v]).is_sat:
        return Classification.CRIMINAL if criminal_possible else Classification.INNOCENT
    return Classification.UNKNOWN


def classify_all(kb: KnowledgeBase) -> dict[str, Classification]:
    """Classify every unresolved cell (row-major)."""
    return {cell: classify(kb, cell) for cell in kb.state.unresolved_cells()}


def check_verdict(state: PublicState, cell: str, status: Status) -> VerdictResult:
    """Judge a user verdict against PUBLIC knowledge only (for the GameEngine).

    An inconsistent KB proves nothing useful, so it is reported as NOT_PROVABLE.
    """
    status = Status(status)
    if cell in state.proved:
        return VerdictResult.ACCEPTED if state.proved[cell] is status else VerdictResult.CONTRADICTED
    forced = classify(build_kb(state), cell).status
    if forced is None:
        return VerdictResult.NOT_PROVABLE
    return VerdictResult.ACCEPTED if forced is status else VerdictResult.CONTRADICTED
