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


def verify_puzzle_file(path: Path) -> dict[str, object]:
    """Verify a single puzzle file across all criteria."""
    result: dict[str, object] = {
        "file": path.name,
        "schema_ok": False,
        "dpll_unique": False,
        "agent_solvable": False,
        "cross_check_ok": False,
        "cross_check_status": "ERR",
        "cross_check_tiers": [],
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
    ran_tiers = {name: cc for name, cc in cc_results.items() if cc.available}
    if not ran_tiers:
        result["cross_check_status"] = "SKIP"
        result["cross_check_ok"] = True
        result["cross_check_tiers"] = []
        result["overall"] = "PASS"
        result["details"] = f"Solved in {len(run.steps)} steps (cc skipped)"
        return result

    failed = [
        (name, cc) for name, cc in ran_tiers.items()
        if not cc.is_unique or not cc.matches_solution
    ]
    if failed:
        name, cc = failed[0]
        result["cross_check_status"] = "ERR"
        result["cross_check_ok"] = False
        result["cross_check_tiers"] = sorted(ran_tiers)
        result["details"] = f"Cross-check {name} failed: unique={cc.is_unique}, match={cc.matches_solution}"
        return result

    tiers_str = "+".join(sorted(ran_tiers))
    result["cross_check_status"] = "OK"
    result["cross_check_ok"] = True
    result["cross_check_tiers"] = sorted(ran_tiers)
    result["overall"] = "PASS"
    result["details"] = f"Solved in {len(run.steps)} steps [{tiers_str}]"
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
    fmt = "{:<32} {:<8} {:<12} {:<14} {:<12} {:<8} {:<36}"
    print(fmt.format("Puzzle File", "Schema", "DPLL Unique", "No-Guess Solv", "Cross-Check", "Result", "Notes"))
    print("-" * 126)

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
            str(res["cross_check_status"]),
            status_str,
            str(res["details"])[:36],
        ))

    print("-" * 126)
    if all_pass:
        print("\nAll puzzles PASSED verification successfully!")
        sys.exit(0)
    else:
        print("\nSome puzzles FAILED verification.")
        sys.exit(1)


if __name__ == "__main__":
    main()
