"""[C] Entailment classification.

    KB |= C_i      <=>  KB AND NOT C_i is UNSAT   -> CRIMINAL
    KB |= NOT C_i  <=>  KB AND C_i     is UNSAT   -> INNOCENT
    both SAT                                      -> UNKNOWN
    KB itself UNSAT                               -> INCONSISTENT
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


def classify(kb: KnowledgeBase, cell: str) -> Classification:
    if not kb.is_consistent():
        return Classification.INCONSISTENT
    v = kb.var_map.var(cell)
    if not kb.query([-v]).is_sat:
        return Classification.CRIMINAL
    if not kb.query([v]).is_sat:
        return Classification.INNOCENT
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
