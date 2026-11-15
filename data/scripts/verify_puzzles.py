"""[E] Check every puzzle: unique solution + solvable without guessing + independent cross-check."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from algorithms.agent.deduction_agent import AgentOutcome, DeductionAgent
from algorithms.agent.uniqueness import check_uniqueness
from algorithms.tests.helpers import FakeEngine
from data.puzzle_loader import PuzzleValidationError, load_puzzle
from data.scripts.cross_checker import cross_check_all


def verify_puzzle_file(path: Path) -> dict[str, str | bool]:
    """Verify a single puzzle file across all criteria."""
    result: dict[str, str | bool] = {
        "file": path.name,
        "schema_ok": False,
        "dpll_unique": False,
        "agent_solvable": False,
        "cross_check_ok": False,
        "overall": "FAIL",
        "details": "",
    }

    try:
        puzzle = load_puzzle(path)
        result["schema_ok"] = True
    except (PuzzleValidationError, Exception) as e:
        result["details"] = f"Schema error: {e}"
        return result

    # 1. DPLL Uniqueness
    initial_known = {c: puzzle.solution[c] for c in puzzle.initially_revealed}
    u_res = check_uniqueness(puzzle.board, puzzle.clues, initial_known)
    if not u_res.is_unique:
        result["details"] = f"DPLL uniqueness failed: {u_res.status.value}"
        return result
    result["dpll_unique"] = True

    # 2. Agent no-guess solvability
    engine = FakeEngine(puzzle.to_dict())
    run = DeductionAgent().run(engine)
    if run.outcome is not AgentOutcome.SOLVED:
        result["details"] = f"Agent not solvable: {run.outcome.value} (steps: {len(run.steps)})"
        return result
    result["agent_solvable"] = True

    # 3. Independent cross-check
    cc_results = cross_check_all(puzzle)
    all_cc_ok = True
    for name, cc in cc_results.items():
        if cc.available and (not cc.is_unique or not cc.matches_solution):
            all_cc_ok = False
            result["details"] = f"Cross-check {name} failed: unique={cc.is_unique}, match={cc.matches_solution}"
            break

    result["cross_check_ok"] = all_cc_ok
    if all_cc_ok:
        result["overall"] = "PASS"
        result["details"] = f"Solved in {len(run.steps)} steps, {u_res.stats.decisions} decisions"

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify all Griductive puzzles")
    parser.add_argument("paths", nargs="*", default=["data/puzzles"],
                        help="Directories or files to check (default: data/puzzles)")
    args = parser.parse_args()

    files = []
    for p_str in args.paths:
        p = Path(p_str)
        if p.is_file() and p.suffix == ".json":
            files.append(p)
        elif p.is_dir():
            files.extend(sorted(p.rglob("*.json")))

    if not files:
        print(f"No JSON puzzle files found in: {args.paths}")
        sys.exit(0)

    print(f"Verifying {len(files)} puzzle files...\n")
    fmt = "{:<32} {:<8} {:<12} {:<14} {:<12} {:<8} {:<25}"
    print(fmt.format("Puzzle File", "Schema", "DPLL Unique", "No-Guess Solv", "Cross-Check", "Result", "Notes"))
    print("-" * 115)

    all_pass = True
    for f in files:
        res = verify_puzzle_file(f)
        status_str = "PASS" if res["overall"] == "PASS" else "FAIL"
        if res["overall"] != "PASS":
            all_pass = False

        print(fmt.format(
            str(res["file"])[:30],
            "OK" if res["schema_ok"] else "ERR",
            "OK" if res["dpll_unique"] else "ERR",
            "OK" if res["agent_solvable"] else "ERR",
            "OK" if res["cross_check_ok"] else "ERR",
            status_str,
            str(res["details"])[:25],
        ))

    print("-" * 115)
    if all_pass:
        print("\nAll puzzles PASSED verification successfully!")
        sys.exit(0)
    else:
        print("\nSome puzzles FAILED verification.")
        sys.exit(1)


if __name__ == "__main__":
    main()
