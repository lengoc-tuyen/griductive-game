"""[E] Run agent on all puzzles; record vars (primary/aux), clauses, SAT calls,
decisions/propagations/backtracks, steps/waves, runtime; keep failures/timeouts.

Section 4.5 Requirements:
1. Number of primary and auxiliary variables.
2. Number of CNF clauses.
3. Number of SAT calls.
4. Decisions, propagations, and backtracks.
5. Number of deduction steps or reveal waves.
6. Runtime.
7. Solver comparison: DPLL vs PySAT (Glucose4) vs Z3.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

from algorithms.agent.deduction_agent import DeductionAgent
from algorithms.agent.uniqueness import check_uniqueness
from algorithms.tests.helpers import FakeEngine
from data.puzzle_loader import load_puzzle
from data.scripts.cross_checker import cross_check_all


def run_benchmark(puzzles_dir: Path, output_csv: Path, time_limit: float = 30.0) -> list[dict]:
    files = sorted(puzzles_dir.rglob("*.json"))
    if not files:
        print(f"No puzzle JSON files found in {puzzles_dir}")
        return []

    print(f"Running experiments on {len(files)} puzzles (time limit: {time_limit}s per puzzle)...")

    results = []
    agent = DeductionAgent(time_limit=time_limit)

    for i, file_path in enumerate(files, 1):
        puzzle = load_puzzle(file_path)
        engine = FakeEngine(puzzle.to_dict())

        # 1. Run DeductionAgent
        agent_run = agent.run(engine)
        summary = agent_run.summary()

        # 2. Complete KB size via check_uniqueness
        initial_known = {c: puzzle.solution[c] for c in puzzle.initially_revealed}
        u_res = check_uniqueness(puzzle.board, puzzle.clues, initial_known)

        # 3. Independent solver cross-checks & runtime
        cc_map = cross_check_all(puzzle)
        z3_time = cc_map.get("z3").runtime_seconds if "z3" in cc_map else None
        pysat_time = cc_map.get("pysat").runtime_seconds if "pysat" in cc_map else None
        bf_time = cc_map.get("brute_force").runtime_seconds if "brute_force" in cc_map else None

        record = {
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
            "dpll_sat_runtime_s": round(float(summary["sat_runtime"]), 5),
            "dpll_total_runtime_s": round(float(summary["runtime"]), 5),
            "pysat_runtime_s": round(pysat_time, 5) if pysat_time is not None else "N/A",
            "z3_runtime_s": round(z3_time, 5) if z3_time is not None else "N/A",
            "brute_force_s": round(bf_time, 5) if bf_time is not None else "N/A",
        }
        results.append(record)

        print(f"[{i:02d}/{len(files):02d}] {puzzle.id} ({puzzle.size}x{puzzle.size}): "
              f"outcome={record['outcome']}, steps={record['steps']}, "
              f"vars={record['total_vars']}, clauses={record['clauses']}, "
              f"DPLL={record['dpll_total_runtime_s']}s, PySAT={record['pysat_runtime_s']}s, Z3={record['z3_runtime_s']}s")

    # Write CSV
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    if results:
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        print(f"\nExperiment benchmark results successfully saved to: {output_csv}")

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full experiments benchmark on puzzles")
    parser.add_argument("--puzzles-dir", type=str, default="data/puzzles",
                        help="Root directory containing puzzle JSONs")
    parser.add_argument("--output-csv", type=str, default="data/results/experiments_benchmark.csv",
                        help="Path to save output benchmark CSV")
    parser.add_argument("--time-limit", type=float, default=30.0,
                        help="Max runtime per puzzle in seconds (default: 30)")
    args = parser.parse_args()

    run_benchmark(Path(args.puzzles_dir), Path(args.output_csv), time_limit=args.time_limit)


if __name__ == "__main__":
    main()
