"""[E] Independent cross-checking module for puzzle verification and benchmark comparison.

Does NOT rely on group's DPLL solver or encoder alone.
Provides 3 independent verification tiers:
1. Semantic Brute Force (pure Python, ground truth for 3x3)
2. PySAT (industrial SAT solver Glucose4 on CNF)
3. Z3 SMT/SAT Solver (independent direct semantic encoder + solver)
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from algorithms.logic.encoder import CNFEncoder
from algorithms.logic.evaluator import evaluate as semantic_evaluate
from algorithms.logic.models import Board, Clue, ClueType, Status
from algorithms.logic.regions import clue_region
from data.puzzle_loader import Puzzle

# Check optional libraries
try:
    import pysat
    from pysat.solvers import Glucose4
    PYSAT_AVAILABLE = True
except ImportError:
    PYSAT_AVAILABLE = False

try:
    import z3
    Z3_AVAILABLE = True
except ImportError:
    Z3_AVAILABLE = False


@dataclass
class CrossCheckResult:
    tier: str
    available: bool
    is_unique: bool
    num_solutions: int
    matches_solution: bool
    runtime_seconds: float
    error_message: Optional[str] = None


def brute_force_verify(puzzle: Puzzle, include_initial: bool = True) -> CrossCheckResult:
    """Tier 1: Semantic Brute Force.

    Checks all 2^(N^2) states against semantic evaluator directly (no CNF).
    Feasible for 3x3 (2^9 = 512 assignments).
    """
    board = puzzle.board
    cells = board.cells()
    num_cells = len(cells)

    if num_cells > 12:
        return CrossCheckResult(
            tier="brute_force",
            available=False,
            is_unique=False,
            num_solutions=0,
            matches_solution=False,
            runtime_seconds=0.0,
            error_message=f"Brute force skipped: 2^{num_cells} assignments is too large.",
        )

    start = time.perf_counter()
    matching_solutions = []

    initial_set = set(puzzle.initially_revealed) if include_initial else set()

    for bit_tuple in itertools.product((False, True), repeat=num_cells):
        assignment = {cell: bit_tuple[i] for i, cell in enumerate(cells)}

        # Filter by initially known statuses
        if include_initial:
            skip = False
            for c in initial_set:
                if assignment[c] != (puzzle.solution[c] is Status.CRIMINAL):
                    skip = True
                    break
            if skip:
                continue

        # Check all clues
        all_true = True
        for clue in puzzle.clues:
            if not semantic_evaluate(clue, board, assignment):
                all_true = False
                break
        if all_true:
            matching_solutions.append(assignment)
            if len(matching_solutions) > 1:
                break

    elapsed = time.perf_counter() - start
    is_unique = len(matching_solutions) == 1
    matches = False
    if is_unique:
        sol = matching_solutions[0]
        matches = all(sol[c] == (puzzle.solution[c] is Status.CRIMINAL) for c in cells)

    return CrossCheckResult(
        tier="brute_force",
        available=True,
        is_unique=is_unique,
        num_solutions=len(matching_solutions),
        matches_solution=matches,
        runtime_seconds=elapsed,
    )


def pysat_verify(puzzle: Puzzle, include_initial: bool = True) -> CrossCheckResult:
    """Tier 2: Industrial SAT solver (Glucose4) via PySAT.

    Takes CNF from encoder and checks for uniqueness using blocking clauses.
    """
    if not PYSAT_AVAILABLE:
        return CrossCheckResult(
            tier="pysat",
            available=False,
            is_unique=False,
            num_solutions=0,
            matches_solution=False,
            runtime_seconds=0.0,
            error_message="python-sat is not installed",
        )

    board = puzzle.board
    encoder = CNFEncoder(board)
    known = {c: puzzle.solution[c] for c in puzzle.initially_revealed} if include_initial else None
    encoded = encoder.encode(puzzle.clues, proved=known)

    start = time.perf_counter()
    solutions = []

    with Glucose4(bootstrap_with=encoded.clauses) as solver:
        while len(solutions) < 2:
            if not solver.solve():
                break
            model = solver.get_model()
            model_set = set(model)
            primary_assignment = {}
            blocking_clause = []
            for cell in board.cells():
                var = encoder.vars.var(cell)
                val = var in model_set
                primary_assignment[cell] = val
                blocking_clause.append(-var if val else var)

            solutions.append(primary_assignment)
            solver.add_clause(blocking_clause)

    elapsed = time.perf_counter() - start
    is_unique = len(solutions) == 1
    matches = False
    if is_unique:
        sol = solutions[0]
        matches = all(sol[c] == (puzzle.solution[c] is Status.CRIMINAL) for c in board.cells())

    return CrossCheckResult(
        tier="pysat",
        available=True,
        is_unique=is_unique,
        num_solutions=len(solutions),
        matches_solution=matches,
        runtime_seconds=elapsed,
    )


def z3_verify(puzzle: Puzzle, include_initial: bool = True) -> CrossCheckResult:
    """Tier 3: Direct SMT formulation via Z3.

    Bypasses CNFEncoder entirely. Translates clue semantics directly to Z3 formulas.
    """
    if not Z3_AVAILABLE:
        return CrossCheckResult(
            tier="z3",
            available=False,
            is_unique=False,
            num_solutions=0,
            matches_solution=False,
            runtime_seconds=0.0,
            error_message="z3-solver is not installed",
        )

    board = puzzle.board
    solver = z3.Solver()

    # Create Boolean variables for each cell: True = CRIMINAL, False = INNOCENT
    z3_vars = {c: z3.Bool(f"C_{c}") for c in board.cells()}

    if include_initial:
        for c in puzzle.initially_revealed:
            is_crim = (puzzle.solution[c] is Status.CRIMINAL)
            solver.add(z3_vars[c] == is_crim)

    def _term(cell: str, count_innocent: bool):
        b = z3_vars[cell]
        return z3.If(b, 0, 1) if count_innocent else z3.If(b, 1, 0)

    # Translate each clue
    for clue in puzzle.clues:
        ctype = clue.type
        params = clue.params
        count_innocent = (params.get("counts") == "INNOCENT")

        if ctype is ClueType.FACT:
            cell = board.cell_of(params["person"])
            is_crim = (Status(params["status"]) is Status.CRIMINAL)
            solver.add(z3_vars[cell] == is_crim)

        elif ctype is ClueType.SAME:
            a = board.cell_of(params["a"])
            b = board.cell_of(params["b"])
            solver.add(z3_vars[a] == z3_vars[b])

        elif ctype is ClueType.DIFFERENT:
            a = board.cell_of(params["a"])
            b = board.cell_of(params["b"])
            solver.add(z3_vars[a] != z3_vars[b])

        elif ctype in (ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST):
            cells = clue_region(clue, board)
            k = params["k"]
            sum_expr = z3.Sum([_term(c, count_innocent) for c in cells]) if cells else 0
            if ctype is ClueType.EXACTLY:
                solver.add(sum_expr == k)
            elif ctype is ClueType.AT_LEAST:
                solver.add(sum_expr >= k)
            elif ctype is ClueType.AT_MOST:
                solver.add(sum_expr <= k)

        elif ctype is ClueType.PARITY:
            cells = clue_region(clue, board)
            sum_expr = z3.Sum([_term(c, count_innocent) for c in cells]) if cells else 0
            want_odd = (params["parity"] == "ODD")
            solver.add((sum_expr % 2) == (1 if want_odd else 0))

        elif ctype is ClueType.COMPARE:
            from algorithms.logic.regions import resolve as resolve_region
            region_a = resolve_region(params["region_a"], board)
            region_b = resolve_region(params["region_b"], board)
            sum_a = z3.Sum([_term(c, count_innocent) for c in region_a]) if region_a else 0
            sum_b = z3.Sum([_term(c, count_innocent) for c in region_b]) if region_b else 0
            op = params["op"]
            if op == "MORE":
                solver.add(sum_a > sum_b)
            elif op == "FEWER":
                solver.add(sum_a < sum_b)
            elif op == "EQUAL":
                solver.add(sum_a == sum_b)

    start = time.perf_counter()
    solutions = []

    while len(solutions) < 2:
        check = solver.check()
        if check != z3.sat:
            break
        model = solver.model()
        assignment = {}
        blocking = []
        for cell in board.cells():
            v = z3_vars[cell]
            val = z3.is_true(model.eval(v, model_completion=True))
            assignment[cell] = val
            blocking.append(v != val)

        solutions.append(assignment)
        solver.add(z3.Or(*blocking))

    elapsed = time.perf_counter() - start
    is_unique = len(solutions) == 1
    matches = False
    if is_unique:
        sol = solutions[0]
        matches = all(sol[c] == (puzzle.solution[c] is Status.CRIMINAL) for c in board.cells())

    return CrossCheckResult(
        tier="z3",
        available=True,
        is_unique=is_unique,
        num_solutions=len(solutions),
        matches_solution=matches,
        runtime_seconds=elapsed,
    )


def cross_check_all(puzzle: Puzzle, include_initial: bool = True) -> dict[str, CrossCheckResult]:
    """Run all available independent cross-checks on a puzzle."""
    results = {}
    if puzzle.size <= 3:
        results["brute_force"] = brute_force_verify(puzzle, include_initial)
    if PYSAT_AVAILABLE:
        results["pysat"] = pysat_verify(puzzle, include_initial)
    if Z3_AVAILABLE:
        results["z3"] = z3_verify(puzzle, include_initial)
    return results
