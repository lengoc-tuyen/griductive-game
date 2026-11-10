"""[A] Cardinality constraints -> CNF, direct combinatorial encoding (no aux vars).

For literals x_1..x_n:

* at_most(k):  every subset S with |S| = k+1 has at least one false literal
               -> for each S: OR_{x in S} NOT x            (C(n, k+1) clauses)
* at_least(k): every subset S with |S| = n-k+1 has at least one true literal
               -> for each S: OR_{x in S} x                (C(n, n-k+1) clauses)
* exactly(k):  at_most(k) AND at_least(k)

Required regions are small (row/col <= 5, neighbors <= 8), so this is fine.
A sequential-counter encoding with aux variables can be added later for big regions.
"""

from __future__ import annotations

from itertools import combinations
from typing import Sequence

Clause = list[int]


def at_most(lits: Sequence[int], k: int) -> list[Clause]:
    n = len(lits)
    if k < 0:
        return [[]]  # impossible
    if k >= n:
        return []
    return [[-x for x in subset] for subset in combinations(lits, k + 1)]


def at_least(lits: Sequence[int], k: int) -> list[Clause]:
    n = len(lits)
    if k <= 0:
        return []
    if k > n:
        return [[]]  # impossible
    return [list(subset) for subset in combinations(lits, n - k + 1)]


def exactly(lits: Sequence[int], k: int) -> list[Clause]:
    return at_most(lits, k) + at_least(lits, k)
