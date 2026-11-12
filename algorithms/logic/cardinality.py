"""[A] Cardinality / parity / comparison constraints -> CNF.

Direct combinatorial encoding (no auxiliary variables) for the core counting clues.
For literals x_1..x_n:

* at_most(k):  every subset S with |S| = k+1 has at least one false literal
               -> for each S: OR_{x in S} NOT x            (C(n, k+1) clauses)
* at_least(k): every subset S with |S| = n-k+1 has at least one true literal
               -> for each S: OR_{x in S} x                (C(n, n-k+1) clauses)
* exactly(k):  at_most(k) AND at_least(k)

Required regions are small (row/col <= 5, neighbors <= 8), so this is fine.

Extensions use Tseitin-style encodings with auxiliary variables (allocated through a
``new_var`` callback so they never collide with the primary variables C_i):

* ``parity``:        XOR chain  p_i <-> p_{i-1} XOR x_i,  then assert p_n (ODD) or NOT p_n (EVEN)
* ``unary_counter``: sequential counter  r[i][j] <-> (x_1 + ... + x_i >= j)
* ``compare``:       two unary counters + "count(A) > count(B)" / "<" / "=" clauses

The Tseitin helpers accept Python ``True`` / ``False`` as constant literals and fold
them away, so no clause ever contains a constant.
"""

from __future__ import annotations

from itertools import combinations
from typing import Callable, Sequence, Union

Clause = list[int]
Lit = Union[int, bool]          # an int literal, or a constant True / False
NewVar = Callable[[], int]


# ----------------------------------------------------------------- direct encodings
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


# -------------------------------------------------------------- constant folding
def _neg(lit: Lit) -> Lit:
    return (not lit) if isinstance(lit, bool) else -lit


def _clause(*lits: Lit) -> list[Clause]:
    """One clause with constants folded: ``[]`` if it is trivially true."""
    out: Clause = []
    for lit in lits:
        if lit is True:
            return []
        if lit is False:
            continue
        out.append(lit)
    return [out]


# ------------------------------------------------------------------------- parity
def parity(lits: Sequence[int], odd: bool, new_var: NewVar) -> list[Clause]:
    """``x_1 XOR ... XOR x_n == odd``  (n - 1 auxiliary variables, 4 clauses each)."""
    if not lits:
        return [[]] if odd else []
    clauses: list[Clause] = []
    acc: int = lits[0]
    for x in lits[1:]:
        p = new_var()
        # p <-> acc XOR x
        clauses += [[-p, acc, x], [-p, -acc, -x], [p, -acc, x], [p, acc, -x]]
        acc = p
    clauses.append([acc] if odd else [-acc])
    return clauses


# --------------------------------------------------------------- unary counter
def unary_counter(lits: Sequence[int], new_var: NewVar) -> tuple[list[Lit], list[Clause]]:
    """Sequential counter with full equivalence.

    Returns ``(geq, clauses)`` where ``geq[j]`` (j = 0..n) is a literal that is true
    iff at least ``j`` of ``lits`` are true (``geq[0]`` is the constant True).
    Recurrence: ``r[i][j] <-> r[i-1][j] OR (x_i AND r[i-1][j-1])``.
    """
    clauses: list[Clause] = []
    prev: list[Lit] = [True]  # counts over the first 0 literals
    for x in lits:
        cur: list[Lit] = [True]
        for j in range(1, len(prev) + 1):
            a = prev[j] if j < len(prev) else False  # r[i-1][j]
            b = prev[j - 1]                          # r[i-1][j-1]
            cur.append(_or_and(a, x, b, new_var, clauses))
        prev = cur
    return prev, clauses


def _or_and(a: Lit, x: int, b: Lit, new_var: NewVar, clauses: list[Clause]) -> Lit:
    """Return a literal equivalent to ``a OR (x AND b)``, adding Tseitin clauses."""
    if a is True:
        return True
    if b is False:
        return a
    if a is False and b is True:
        return x
    out = new_var()
    clauses += _clause(_neg(a), out)              # a            -> out
    clauses += _clause(-x, _neg(b), out)          # x AND b      -> out
    clauses += _clause(-out, a, x)                # out -> a OR x
    clauses += _clause(-out, a, b)                # out -> a OR b
    return out


def _geq(counter: Sequence[Lit], j: int) -> Lit:
    if j <= 0:
        return True
    return counter[j] if j < len(counter) else False


def compare(lits_a: Sequence[int], lits_b: Sequence[int], op: str, new_var: NewVar) -> list[Clause]:
    """``count(A) op count(B)`` with ``op`` in ``MORE`` (>), ``FEWER`` (<), ``EQUAL`` (=)."""
    if op == "FEWER":
        return compare(lits_b, lits_a, "MORE", new_var)
    ga, clauses = unary_counter(lits_a, new_var)
    gb, more = unary_counter(lits_b, new_var)
    clauses += more
    if op == "MORE":
        # count(A) >= count(B) + 1  <=>  for every j: count(B) >= j  ->  count(A) >= j + 1
        for j in range(0, len(lits_b) + 1):
            clauses += _clause(_neg(_geq(gb, j)), _geq(ga, j + 1))
    elif op == "EQUAL":
        for j in range(1, max(len(lits_a), len(lits_b)) + 1):
            a, b = _geq(ga, j), _geq(gb, j)
            clauses += _clause(_neg(a), b) + _clause(a, _neg(b))
    else:
        raise ValueError(f"unknown comparison {op!r}")
    return clauses
