"""[B] Branching heuristics.

Default (required by the spec: deterministic): the lowest-index unassigned variable
that occurs in a not-yet-satisfied clause. Fancier heuristics are optional.
"""

from __future__ import annotations

from typing import Mapping, Sequence


def lowest_index(clauses: Sequence[Sequence[int]], assignment: Mapping[int, bool]) -> int | None:
    best: int | None = None
    for cl in clauses:
        if any(assignment.get(abs(l)) == (l > 0) for l in cl):
            continue  # clause already satisfied
        for l in cl:
            v = abs(l)
            if v not in assignment and (best is None or v < best):
                best = v
    return best
