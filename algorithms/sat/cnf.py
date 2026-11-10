"""[B] CNF helpers: normalisation and DIMACS I/O.

A clause is a list of non-zero ints (DIMACS style); a formula is a list of clauses.
"""

from __future__ import annotations

from typing import Iterable

Clause = list[int]


def normalize(clauses: Iterable[Iterable[int]]) -> tuple[list[Clause], bool]:
    """Drop duplicate literals and tautologies.

    Returns ``(clauses, has_empty)``; ``has_empty`` is True if some clause is empty
    (the formula is then trivially UNSAT).
    """
    out: list[Clause] = []
    has_empty = False
    for cl in clauses:
        lits: list[int] = []
        seen: set[int] = set()
        tautology = False
        for lit in cl:
            if lit == 0:
                raise ValueError("literal 0 is not allowed")
            if -lit in seen:
                tautology = True
                break
            if lit not in seen:
                seen.add(lit)
                lits.append(lit)
        if tautology:
            continue
        if not lits:
            has_empty = True
        out.append(lits)
    return out, has_empty


def max_var(clauses: Iterable[Iterable[int]]) -> int:
    return max((abs(l) for cl in clauses for l in cl), default=0)


def to_dimacs(clauses: list[Clause], num_vars: int | None = None) -> str:
    n = max_var(clauses) if num_vars is None else num_vars
    lines = [f"p cnf {n} {len(clauses)}"]
    lines += [" ".join(map(str, cl)) + " 0" for cl in clauses]
    return "\n".join(lines) + "\n"


def from_dimacs(text: str) -> tuple[list[Clause], int]:
    clauses: list[Clause] = []
    num_vars = 0
    cur: Clause = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("c"):
            continue
        if line.startswith("p"):
            num_vars = int(line.split()[2])
            continue
        for tok in line.split():
            lit = int(tok)
            if lit == 0:
                clauses.append(cur)
                cur = []
            else:
                cur.append(lit)
    if cur:
        clauses.append(cur)
    return clauses, max(num_vars, max_var(clauses))
