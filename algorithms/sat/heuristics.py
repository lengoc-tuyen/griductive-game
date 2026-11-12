"""[B] Branching heuristics (all deterministic).

A heuristic is computed once per formula and returns a static branching ORDER over
the variables that occur in it; the solver always branches on the first variable
of that order that is still unassigned. Static orders keep variable selection
O(1) amortised and make every run reproducible.

* ``lowest_index`` (default): 1, 2, 3, ... - primary variables C_i come first,
  auxiliary variables (numbered after them) last, so aux vars are usually fixed by
  unit propagation instead of being branched on.
* ``most_occurrences``: variables in more clauses first (ties: lower index).
* ``jeroslow_wang``: score sum 2^-|clause| over clauses containing the variable
  (short clauses weigh more; ties: lower index).
"""

from __future__ import annotations

from collections import Counter
from typing import Callable, Sequence

Order = Callable[[Sequence[Sequence[int]]], list[int]]


def _variables(clauses: Sequence[Sequence[int]]) -> set[int]:
    return {abs(lit) for cl in clauses for lit in cl}


def lowest_index(clauses: Sequence[Sequence[int]]) -> list[int]:
    return sorted(_variables(clauses))


def most_occurrences(clauses: Sequence[Sequence[int]]) -> list[int]:
    occ = Counter(abs(lit) for cl in clauses for lit in cl)
    return sorted(occ, key=lambda v: (-occ[v], v))


def jeroslow_wang(clauses: Sequence[Sequence[int]]) -> list[int]:
    score: dict[int, float] = {}
    for cl in clauses:
        w = 2.0 ** -len(cl)
        for lit in cl:
            score[abs(lit)] = score.get(abs(lit), 0.0) + w
    return sorted(score, key=lambda v: (-score[v], v))


HEURISTICS: dict[str, Order] = {
    "lowest_index": lowest_index,
    "most_occurrences": most_occurrences,
    "jeroslow_wang": jeroslow_wang,
}


def get(name: str) -> Order:
    try:
        return HEURISTICS[name]
    except KeyError:
        raise ValueError(f"unknown heuristic {name!r}; choose from {sorted(HEURISTICS)}") from None
