"""[C] Hint: one currently forced character + the revealed clues that justify it.

Uses the PUBLIC state only (never the hidden solution):

1. find the first forced verdict (row-major), exactly like the agent;
2. shrink its support by deletion: drop each revealed clue / proved verdict in turn
   and keep it dropped if ``support AND (opposite verdict)`` is still UNSAT.

The result is an irredundant set of facts (removing any one of them would make the
verdict unprovable), which the GUI can highlight as "look at these clues".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from algorithms.agent.deduction_agent import find_forced
from algorithms.agent.knowledge_base import build_kb
from algorithms.agent.public_state import PublicState
from algorithms.logic.models import Status
from algorithms.sat.dpll import DPLLSolver

_VERDICT = "verdict:"


@dataclass(frozen=True)
class Hint:
    cell: str
    status: Status
    clue_ids: tuple[str, ...]      # revealed clues the proof needs
    proved_cells: tuple[str, ...]  # already proved verdicts the proof needs
    sat_calls: int

    def message(self, state: PublicState) -> str:
        name = state.board.character_at(self.cell).name
        why = list(self.clue_ids) + [f"{c} is {state.proved[c].value.lower()}" for c in self.proved_cells]
        return (f"{name} ({self.cell}) can be proved {self.status.value}"
                + (f" using: {', '.join(why)}" if why else ""))


def hint(state: PublicState, explain: bool = True) -> Optional[Hint]:
    """Return the next provable verdict (with its supporting clues), or None.

    Raises ``ValueError`` if the public knowledge is inconsistent.
    """
    kb = build_kb(state)
    forced = find_forced(kb)
    sat_calls = kb.sat_calls
    if forced is None:
        return None
    if not explain:
        return Hint(forced.cell, forced.status, (), (), sat_calls)

    groups: dict[str, list[list[int]]] = {}
    for clause, origin in zip(kb.cnf.clauses, kb.cnf.clause_origin):
        groups.setdefault(origin, []).append(clause)
    v = kb.var_map.var(forced.cell)
    refute = [-v] if forced.status is Status.CRIMINAL else [v]

    keep = list(groups)
    for origin in list(keep):
        trial = [o for o in keep if o != origin]
        clauses = [cl for o in trial for cl in groups[o]]
        sat_calls += 1
        if not DPLLSolver(clauses, kb.cnf.num_vars).solve(refute).is_sat:
            keep = trial

    clue_ids = tuple(o for o in keep if not o.startswith(_VERDICT))
    proved = tuple(o[len(_VERDICT):] for o in keep if o.startswith(_VERDICT))
    return Hint(forced.cell, forced.status, clue_ids, proved, sat_calls)
