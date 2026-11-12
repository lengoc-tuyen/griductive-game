"""[C] Deduction trace: step number, active clue ids, SAT queries, verdict, revealed clue.

``DeductionTrace.to_text()`` gives a human-readable log (GUI / report),
``to_dict()`` a JSON-serialisable form (experiments).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from algorithms.logic.models import Clue, Status
from algorithms.sat.stats import SolverStats


@dataclass
class SatQuery:
    """One call to the SAT solver: ``KB_t AND assumptions``."""

    assumptions: tuple[int, ...]
    description: str          # e.g. "KB AND NOT C[A1]"
    sat: bool
    stats: SolverStats

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.description, "assumptions": list(self.assumptions),
                "result": "SAT" if self.sat else "UNSAT", **self.stats.as_dict()}


@dataclass
class TraceStep:
    index: int
    cell: str
    verdict: Status
    active_clue_ids: list[str]
    queries: list[SatQuery]
    num_primary: int
    num_aux: int
    num_clauses: int
    revealed_clue: Optional[Clue] = None

    @property
    def sat_calls(self) -> int:
        return len(self.queries)

    @property
    def revealed_clue_id(self) -> Optional[str]:
        return self.revealed_clue.id if self.revealed_clue is not None else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.index,
            "cell": self.cell,
            "verdict": self.verdict.value,
            "active_clues": list(self.active_clue_ids),
            "kb": {"primary_vars": self.num_primary, "aux_vars": self.num_aux, "clauses": self.num_clauses},
            "sat_queries": [q.to_dict() for q in self.queries],
            "revealed_clue": self.revealed_clue.to_dict() if self.revealed_clue else None,
        }


@dataclass
class DeductionTrace:
    steps: list[TraceStep] = field(default_factory=list)
    outcome: str = ""
    final_queries: list[SatQuery] = field(default_factory=list)  # queries of the last, stopping round

    def to_dict(self) -> dict[str, Any]:
        return {"outcome": self.outcome, "steps": [s.to_dict() for s in self.steps],
                "final_queries": [q.to_dict() for q in self.final_queries]}

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_text(self, show_queries: bool = True) -> str:
        lines = []
        for s in self.steps:
            lines.append(f"Step {s.index}: {s.cell} = {s.verdict.value}   "
                         f"(active clues: {', '.join(s.active_clue_ids) or '-'}; "
                         f"KB {s.num_primary}+{s.num_aux} vars, {s.num_clauses} clauses; "
                         f"{s.sat_calls} SAT calls)")
            if show_queries:
                lines += [f"    {q.description:<28} -> {'SAT' if q.sat else 'UNSAT'}" for q in s.queries]
            lines.append(f"    revealed: {s.revealed_clue_id or '(no clue)'}")
        if show_queries and self.final_queries:
            lines.append("Final round:")
            lines += [f"    {q.description:<28} -> {'SAT' if q.sat else 'UNSAT'}" for q in self.final_queries]
        lines.append(f"Outcome: {self.outcome}")
        return "\n".join(lines)
