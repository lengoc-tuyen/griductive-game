"""[E] Run experiments for Section 4.5 & 4.6.

Produces three clean CSV reports in ``data/results/``:
  1. ``experiments_benchmark.csv``: All 6 required metrics across all puzzles, separating
     Deduction-Loop metrics from Same-Task Complete-KB Uniqueness Check runtime
     (DPLL vs PySAT vs Z3 vs BruteForce).
  2. ``experiments_heuristics.csv``: Comparison of all 3 deterministic DPLL heuristics
     (``lowest_index``, ``most_occurrences``, ``jeroslow_wang``) on the SAME puzzle set.
  3. ``experiments_edge_cases.csv``: Explicitly records failure / non-trivial terminal
     outcomes (``STUCK``, ``INCONSISTENT``, ``TIMEOUT``, ``STEP_LIMIT``, and 5x5 stress).
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path
from typing import Iterable, Mapping, Optional

from algorithms.agent.deduction_agent import AgentOutcome, AgentRun, DeductionAgent, find_forced
from algorithms.agent.knowledge_base import build_kb
from algorithms.agent.public_state import EngineProtocol, VerdictResult
from algorithms.agent.trace import TraceStep
from algorithms.agent.uniqueness import Uniqueness, UniquenessResult
from algorithms.logic.encoder import CNFEncoder
from algorithms.logic.models import Board, Clue, Status
from algorithms.sat.dpll import DPLLSolver, SolverTimeout
from algorithms.sat.stats import SolverStats
from algorithms.tests.helpers import FakeEngine
from data.puzzle_loader import load_puzzle
from data.scripts.cross_checker import cross_check_all

HEURISTICS = ("lowest_index", "most_occurrences", "jeroslow_wang")


def run_agent_with_heuristic(
    engine: EngineProtocol,
    heuristic: str = "lowest_index",
    max_steps: int | None = None,
    time_limit: float | None = None,
) -> AgentRun:
    """Run the exact DeductionAgent loop using a chosen DPLL heuristic."""
    start = time.perf_counter()
    deadline = None if time_limit is None else start + time_limit
    run = AgentRun(outcome=AgentOutcome.STUCK)
    try:
        while True:
            state = engine.public_state()
            if state.is_solved():
                run.outcome = AgentOutcome.SOLVED
                break
            if max_steps is not None and len(run.steps) >= max_steps:
                run.outcome = AgentOutcome.STEP_LIMIT
                break

            kb = build_kb(state, deadline)
            kb._solver = DPLLSolver(kb.cnf.clauses, kb.cnf.num_vars, heuristic=heuristic)
            try:
                forced = find_forced(kb)
            except ValueError:
                run._absorb(kb)
                run.trace.final_queries = list(kb.queries)
                run.outcome = AgentOutcome.INCONSISTENT
                break
            except SolverTimeout as e:
                kb.stats.merge(e.stats)
                run._absorb(kb)
                run.trace.final_queries = list(kb.queries)
                run.outcome = AgentOutcome.TIMEOUT
                break

            if forced is None:
                run._absorb(kb)
                run.trace.final_queries = list(kb.queries)
                run.outcome = AgentOutcome.STUCK
                break

            run._absorb(kb)
            result, clue = engine.submit(forced.cell, forced.status)
            if result is not VerdictResult.ACCEPTED:
                run.outcome = AgentOutcome.REJECTED
                break
            run.trace.steps.append(
                TraceStep(
                    index=len(run.steps) + 1,
                    cell=forced.cell,
                    verdict=forced.status,
                    active_clue_ids=state.clue_ids(),
                    queries=list(kb.queries),
                    num_primary=kb.num_primary,
                    num_aux=kb.num_aux,
                    num_clauses=kb.num_clauses,
                    revealed_clue=clue,
                )
            )
    finally:
        run.runtime = time.perf_counter() - start
        run.trace.outcome = run.outcome.value
    return run


def dpll_uniqueness_with_heuristic(
    board: Board,
    clues: Iterable[Clue],
    known: Optional[Mapping[str, Status]] = None,
    heuristic: str = "lowest_index",
) -> UniquenessResult:
    """Complete-KB uniqueness check using DPLLSolver with the specified heuristic."""
    encoder = CNFEncoder(board)
    encoded = encoder.encode(clues, known)
    solver = DPLLSolver(encoded.clauses, encoded.num_vars, heuristic=heuristic)
    cells = board.cells()
    stats = SolverStats()
    solutions: list[dict[str, Status]] = []
    sat_calls = 0
    while len(solutions) < 2:
        result = solver.solve()
        sat_calls += 1
        stats.merge(result.stats)
        if not result.is_sat:
            break
        values = {c: result.model[encoder.vars.var(c)] for c in cells}
        solutions.append({c: Status.CRIMINAL if val else Status.INNOCENT for c, val in values.items()})
        solver.add_clause([-encoder.vars.var(c) if val else encoder.vars.var(c) for c, val in values.items()])

    status = (
        Uniqueness.NO_SOLUTION
        if not solutions
        else Uniqueness.UNIQUE
        if len(solutions) == 1
        else Uniqueness.MULTIPLE
    )
    return UniquenessResult(
        status, solutions, sat_calls, encoded.num_primary, encoded.num_aux, encoded.num_clauses, stats
    )


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run_benchmark(
    puzzles_dir: Path,
    output_csv: Path,
    time_limit: float = 30.0,
    edge_cases_dir: Optional[Path] = None,
    heuristics_csv: Optional[Path] = None,
    edge_cases_csv: Optional[Path] = None,
) -> list[dict[str, object]]:
    files = sorted(puzzles_dir.rglob("*.json"))
    if not files:
        print(f"No puzzle JSON files found in {puzzles_dir}")
        return []

    print(f"Running main & heuristic experiments on {len(files)} puzzles (time limit: {time_limit}s)...")
    main_results: list[dict[str, object]] = []
    heuristic_results: list[dict[str, object]] = []

    for i, file_path in enumerate(files, 1):
        puzzle = load_puzzle(file_path)
        initial_known = {c: puzzle.solution[c] for c in puzzle.initially_revealed}

        # Run all 3 heuristics on the exact same puzzle
        runs_by_h: dict[str, AgentRun] = {}
        uniq_by_h: dict[str, UniquenessResult] = {}
        for h in HEURISTICS:
            engine = FakeEngine(puzzle.to_dict())
            h_run = run_agent_with_heuristic(engine, heuristic=h, time_limit=time_limit)
            h_uniq = dpll_uniqueness_with_heuristic(puzzle.board, puzzle.clues, initial_known, heuristic=h)
            runs_by_h[h] = h_run
            uniq_by_h[h] = h_uniq
            s = h_run.summary()
            heuristic_results.append({
                "puzzle_id": puzzle.id,
                "size": puzzle.size,
                "difficulty": puzzle.difficulty or "N/A",
                "heuristic": h,
                "outcome": s["outcome"],
                "steps": s["steps"],
                "primary_vars": h_uniq.num_primary,
                "aux_vars": h_uniq.num_aux,
                "clauses": h_uniq.num_clauses,
                "sat_calls": s["sat_calls"],
                "decisions": s["decisions"],
                "propagations": s["propagations"],
                "backtracks": s["backtracks"],
                "conflicts": s["conflicts"],
                "sat_runtime_s": round(float(s["sat_runtime"]), 5),
                "total_runtime_s": round(float(s["runtime"]), 5),
                "unique_decisions": h_uniq.stats.decisions,
                "unique_backtracks": h_uniq.stats.backtracks,
                "unique_runtime_s": round(h_uniq.stats.runtime, 5),
            })

        # Main benchmark record uses default heuristic ('lowest_index') + same-task Uniqueness comparisons
        agent_run = runs_by_h["lowest_index"]
        summary = agent_run.summary()
        u_res = uniq_by_h["lowest_index"]
        cc_map = cross_check_all(puzzle)

        pysat_res = cc_map.get("pysat")
        z3_res = cc_map.get("z3")
        bf_res = cc_map.get("brute_force")

        record: dict[str, object] = {
            "puzzle_id": puzzle.id,
            "size": puzzle.size,
            "difficulty": puzzle.difficulty or "N/A",
            "num_clues": len(puzzle.clues),
            "outcome": summary["outcome"],
            "steps": summary["steps"],
            "primary_vars": u_res.num_primary,
            "aux_vars": u_res.num_aux,
            "total_vars": u_res.num_primary + u_res.num_aux,
            "clauses": u_res.num_clauses,
            "sat_calls": summary["sat_calls"],
            "decisions": summary["decisions"],
            "propagations": summary["propagations"],
            "backtracks": summary["backtracks"],
            "conflicts": summary["conflicts"],
            "dpll_agent_sat_runtime_s": round(float(summary["sat_runtime"]), 5),
            "dpll_agent_total_runtime_s": round(float(summary["runtime"]), 5),
            "dpll_unique_s": round(u_res.stats.runtime, 5),
            "pysat_unique_s": round(pysat_res.runtime_seconds, 5) if pysat_res and pysat_res.available else "N/A",
            "z3_unique_s": round(z3_res.runtime_seconds, 5) if z3_res and z3_res.available else "N/A",
            "brute_force_unique_s": round(bf_res.runtime_seconds, 5) if bf_res and bf_res.available else "N/A",
        }
        main_results.append(record)

        print(
            f"[{i:02d}/{len(files):02d}] {puzzle.id} ({puzzle.size}x{puzzle.size}): "
            f"outcome={record['outcome']}, steps={record['steps']}, "
            f"vars={record['primary_vars']}+{record['aux_vars']}, clauses={record['clauses']}, "
            f"Agent={record['dpll_agent_total_runtime_s']}s, "
            f"Uniq(DPLL/PySAT/Z3)={record['dpll_unique_s']}/{record['pysat_unique_s']}/{record['z3_unique_s']}"
        )

    _write_csv(output_csv, main_results)
    print(f"\nSaved main benchmark CSV -> {output_csv}")

    if heuristics_csv is not None:
        _write_csv(heuristics_csv, heuristic_results)
        print(f"Saved heuristics benchmark CSV -> {heuristics_csv}")

    if edge_cases_dir is not None and edge_cases_csv is not None:
        edge_rows = run_edge_cases_benchmark(edge_cases_dir)
        _write_csv(edge_cases_csv, edge_rows)
        print(f"Saved edge-cases benchmark CSV -> {edge_cases_csv}")

    return main_results


def run_edge_cases_benchmark(edge_cases_dir: Path) -> list[dict[str, object]]:
    """Run DeductionAgent across failure, stuck, inconsistent, timeout, and step-limit cases."""
    files = sorted(edge_cases_dir.glob("*.json"))
    if not files:
        print(f"No edge-case JSON files found in {edge_cases_dir}")
        return []

    print(f"\nRunning edge-case / failure benchmark on {len(files)} files...")
    rows: list[dict[str, object]] = []

    def _run_scenario(
        file_path: Path,
        scenario: str,
        expected_outcome: str,
        time_limit: float = 30.0,
        max_steps: Optional[int] = None,
    ) -> None:
        puzzle = load_puzzle(file_path)
        initial_known = {c: puzzle.solution[c] for c in puzzle.initially_revealed}
        u_res = dpll_uniqueness_with_heuristic(puzzle.board, puzzle.clues, initial_known)
        engine = FakeEngine(puzzle.to_dict())
        run = DeductionAgent(max_steps=max_steps, time_limit=time_limit).run(engine)
        s = run.summary()
        note = (puzzle.metadata or {}).get("reason", "")
        if scenario != "default":
            note = f"{scenario}; {note}".strip("; ")
        rows.append({
            "case_id": puzzle.id,
            "size": puzzle.size,
            "scenario": scenario,
            "expected_outcome": expected_outcome,
            "actual_outcome": s["outcome"],
            "uniqueness_status": u_res.status.value,
            "steps": s["steps"],
            "primary_vars": u_res.num_primary,
            "aux_vars": u_res.num_aux,
            "clauses": u_res.num_clauses,
            "sat_calls": s["sat_calls"],
            "decisions": s["decisions"],
            "propagations": s["propagations"],
            "backtracks": s["backtracks"],
            "runtime_s": round(float(s["runtime"]), 5),
            "notes": note,
        })
        print(
            f"  [EDGE] {puzzle.id} ({scenario}): outcome={s['outcome']} (expected={expected_outcome}), "
            f"unique={u_res.status.value}, steps={s['steps']}, dec={s['decisions']}, t={round(float(s['runtime']), 5)}s"
        )

    for file_path in files:
        stem = file_path.stem
        if "stuck" in stem:
            _run_scenario(file_path, "missing_clues", "STUCK", time_limit=30.0)
        elif "inconsistent" in stem:
            _run_scenario(file_path, "contradictory_clues", "INCONSISTENT", time_limit=30.0)
        elif "stress" in stem:
            _run_scenario(file_path, "stress_normal_30s", "SOLVED", time_limit=30.0)
            _run_scenario(file_path, "tight_time_limit_0s", "TIMEOUT", time_limit=0.0)
            _run_scenario(file_path, "step_limit_5", "STEP_LIMIT", time_limit=30.0, max_steps=5)
        else:
            _run_scenario(file_path, "default", "UNKNOWN", time_limit=30.0)

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full experiments benchmark on puzzles & edge cases")
    parser.add_argument("--puzzles-dir", type=str, default="data/puzzles",
                        help="Root directory containing playable puzzle JSONs")
    parser.add_argument("--edge-cases-dir", type=str, default="data/edge_cases",
                        help="Directory containing edge/failure case JSONs")
    parser.add_argument("--out-dir", type=str, default="data/results",
                        help="Directory for all CSV outputs (default: data/results)")
    parser.add_argument("--output-csv", type=str, default=None,
                        help="Optional explicit path for main benchmark CSV")
    parser.add_argument("--time-limit", type=float, default=30.0,
                        help="Max runtime per puzzle in seconds (default: 30)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    main_csv = Path(args.output_csv) if args.output_csv else out_dir / "experiments_benchmark.csv"
    heur_csv = out_dir / "experiments_heuristics.csv"
    edge_dir = Path(args.edge_cases_dir) if args.edge_cases_dir else None
    edge_csv = out_dir / "experiments_edge_cases.csv" if edge_dir and edge_dir.exists() else None

    run_benchmark(
        puzzles_dir=Path(args.puzzles_dir),
        output_csv=main_csv,
        time_limit=args.time_limit,
        edge_cases_dir=edge_dir,
        heuristics_csv=heur_csv,
        edge_cases_csv=edge_csv,
    )


if __name__ == "__main__":
    main()
