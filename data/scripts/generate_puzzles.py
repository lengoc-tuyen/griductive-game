"""[E] Puzzle Generator CLI Script.

Generates valid, no-guess solvable, uniquely satisfiable Griductive puzzles
for 3x3, 4x4, and 5x5 boards, with independent cross-checking and difficulty rating.
"""

from __future__ import annotations

import argparse
import csv
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from algorithms.agent.deduction_agent import AgentOutcome, DeductionAgent
from algorithms.agent.entailment import classify
from algorithms.agent.knowledge_base import build_kb
from algorithms.agent.public_state import PublicState
from algorithms.agent.uniqueness import check_uniqueness
from algorithms.logic.evaluator import evaluate as semantic_evaluate
from algorithms.logic.models import Board, Character, Clue, ClueType, Status, make_cell, parse_cell
from algorithms.logic.regions import clue_region, neighbors_of
from algorithms.tests.helpers import FakeEngine
from data.puzzle_loader import Puzzle, save_puzzle
from data.scripts.cross_checker import cross_check_all
from data.scripts.names_pool import generate_characters


def _count_criminals(solution: Mapping[str, Status], cells: Sequence[str], count_innocent: bool = False) -> int:
    target = Status.INNOCENT if count_innocent else Status.CRIMINAL
    return sum(1 for c in cells if solution[c] is target)


def _generate_candidate_clue(
    owner: str,
    target_cell: str,
    board: Board,
    solution: Mapping[str, Status],
    proved_cells: set[str],
    difficulty: str,
    rng: random.Random,
    clue_id: str,
) -> Clue:
    """Generate a valid clue owned by `owner` that provides strong constraint towards `target_cell`."""
    target_status = solution[target_cell]
    target_name = board.character_at(target_cell).name
    owner_name = board.character_at(owner).name

    # Select pool of types according to difficulty
    if difficulty == "EASY":
        types = [ClueType.FACT, ClueType.SAME, ClueType.DIFFERENT, ClueType.EXACTLY]
        weights = [0.30, 0.30, 0.20, 0.20]
    elif difficulty == "MEDIUM":
        types = [ClueType.SAME, ClueType.DIFFERENT, ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST]
        weights = [0.20, 0.20, 0.30, 0.15, 0.15]
    else:  # HARD
        types = [ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST, ClueType.PARITY, ClueType.COMPARE, ClueType.SAME]
        weights = [0.25, 0.20, 0.20, 0.15, 0.10, 0.10]

    chosen_type = rng.choices(types, weights=weights, k=1)[0]
    counts_innocent = (difficulty == "HARD" and rng.random() < 0.25)

    if chosen_type is ClueType.FACT:
        return Clue(
            id=clue_id,
            owner=owner,
            type=ClueType.FACT,
            params={"person": target_name, "status": target_status.value},
        )

    if chosen_type in (ClueType.SAME, ClueType.DIFFERENT):
        ref_cell = owner if owner in proved_cells else (rng.choice(list(proved_cells)) if proved_cells else owner)
        if ref_cell == target_cell:
            candidates = [c for c in board.cells() if c != target_cell]
            ref_cell = rng.choice(candidates)
        ref_name = board.character_at(ref_cell).name
        same = (solution[target_cell] == solution[ref_cell])
        actual_type = ClueType.SAME if same else ClueType.DIFFERENT
        return Clue(
            id=clue_id,
            owner=owner,
            type=actual_type,
            params={"a": target_name, "b": ref_name},
        )

    if chosen_type in (ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST, ClueType.PARITY):
        # Prefer a region where other cells are proved so target is immediately or closely entailed
        c_idx, r_idx = parse_cell(target_cell)
        row_cells = [make_cell(c, r_idx) for c in range(board.size)]
        col_cells = [make_cell(c_idx, r) for r in range(board.size)]

        region_options = []
        # If all other cells in row are proved
        if all(c in proved_cells for c in row_cells if c != target_cell):
            region_options.append({"kind": "row", "row": r_idx + 1})
        # If all other cells in col are proved
        if all(c in proved_cells for c in col_cells if c != target_cell):
            region_options.append({"kind": "col", "col": chr(ord("A") + c_idx)})

        # Explicit cells pairing target with 1 or 2 proved cells
        if proved_cells:
            ref_proved = [owner] if (owner in proved_cells and owner != target_cell) else []
            other_proved = [p for p in proved_cells if p != target_cell and p != owner]
            if other_proved:
                ref_proved.append(rng.choice(other_proved))
            if not ref_proved and proved_cells:
                ref_proved = [rng.choice(list(proved_cells))]
            subset = sorted(list(set(ref_proved + [target_cell])))
            if len(subset) >= 2:
                region_options.append({"kind": "cells", "cells": subset})

        # If neighbors of a proved cell have only target unproved
        for p in proved_cells:
            nb = neighbors_of(p, board)
            if target_cell in nb and sum(1 for n in nb if n not in proved_cells) <= 2:
                region_options.append({"kind": "neighbors", "of": p})
                break

        if not region_options:
            # Fallback explicit cells with owner and target
            region_options.append({"kind": "cells", "cells": sorted([owner, target_cell])})

        region_spec = rng.choice(region_options)
        dummy_clue = Clue("tmp", owner, ClueType.EXACTLY, {"region": region_spec})
        reg_cells = clue_region(dummy_clue, board)
        k_actual = _count_criminals(solution, reg_cells, count_innocent=counts_innocent)

        params: dict[str, Any] = {"region": region_spec}
        if counts_innocent:
            params["counts"] = "INNOCENT"

        if chosen_type is ClueType.EXACTLY:
            params["k"] = k_actual
            return Clue(clue_id, owner, ClueType.EXACTLY, params)

        if chosen_type is ClueType.AT_LEAST:
            k = k_actual if k_actual > 0 else 0
            params["k"] = k
            return Clue(clue_id, owner, ClueType.AT_LEAST, params)

        if chosen_type is ClueType.AT_MOST:
            k = k_actual if k_actual < len(reg_cells) else len(reg_cells)
            params["k"] = k
            return Clue(clue_id, owner, ClueType.AT_MOST, params)

        if chosen_type is ClueType.PARITY:
            params["parity"] = "ODD" if k_actual % 2 == 1 else "EVEN"
            return Clue(clue_id, owner, ClueType.PARITY, params)

    if chosen_type is ClueType.COMPARE:
        reg_a = {"kind": "cells", "cells": [target_cell]}
        ref_cell = owner if owner in proved_cells else rng.choice(list(proved_cells))
        reg_b = {"kind": "cells", "cells": [ref_cell]}
        cnt_a = _count_criminals(solution, [target_cell], counts_innocent)
        cnt_b = _count_criminals(solution, [ref_cell], counts_innocent)
        op = "EQUAL" if cnt_a == cnt_b else ("MORE" if cnt_a > cnt_b else "FEWER")
        params = {"region_a": reg_a, "region_b": reg_b, "op": op}
        if counts_innocent:
            params["counts"] = "INNOCENT"
        return Clue(clue_id, owner, ClueType.COMPARE, params)

    # Fallback FACT
    return Clue(clue_id, owner, ClueType.FACT, {"person": target_name, "status": target_status.value})


def _fill_valid_filler_clue(owner: str, board: Board, solution: Mapping[str, Status],
                            rng: random.Random, clue_id: str) -> Clue:
    """Generate any semantically true clue for card `owner` that doesn't have one."""
    c_idx, r_idx = parse_cell(owner)
    kind = rng.choice(["row", "col", "neighbors"])
    if kind == "row":
        reg = {"kind": "row", "row": r_idx + 1}
    elif kind == "col":
        reg = {"kind": "col", "col": chr(ord("A") + c_idx)}
    else:
        reg = {"kind": "neighbors", "of": owner}

    dummy = Clue("tmp", owner, ClueType.EXACTLY, {"region": reg})
    reg_cells = clue_region(dummy, board)
    k = _count_criminals(solution, reg_cells)
    return Clue(clue_id, owner, ClueType.EXACTLY, {"region": reg, "k": k})


def _score_puzzle(puzzle: Puzzle, run: Any) -> tuple[float, str]:
    """Compute difficulty score and classification."""
    steps = len(run.steps)
    decisions = run.stats.decisions
    backtracks = run.stats.backtracks
    propagations = run.stats.propagations

    clue_complexity = 0.0
    for clue in puzzle.clues:
        if clue.type is ClueType.FACT:
            clue_complexity += 1.0
        elif clue.type in (ClueType.SAME, ClueType.DIFFERENT):
            clue_complexity += 1.5
        elif clue.type is ClueType.EXACTLY:
            kind = clue.params.get("region", {}).get("kind", "")
            clue_complexity += 2.0 if kind in ("row", "col") else 3.5
        elif clue.type in (ClueType.AT_LEAST, ClueType.AT_MOST):
            clue_complexity += 3.0
        elif clue.type in (ClueType.PARITY, ClueType.COMPARE):
            clue_complexity += 5.0

    raw_score = (
        steps * 1.5
        + decisions * 0.4
        + backtracks * 4.0
        + (clue_complexity / max(1, len(puzzle.clues))) * 5.0
        - len(puzzle.initially_revealed) * 2.0
    )

    if raw_score < 18.0:
        cat = "EASY"
    elif raw_score < 35.0:
        cat = "MEDIUM"
    else:
        cat = "HARD"

    return round(raw_score, 2), cat


def minimize_clues(puzzle: Puzzle) -> Puzzle:
    """Tối giản clue: Thử bỏ từng clue một, clue nào bỏ đi mà vẫn duy nhất nghiệm

    và vẫn giải được không đoán (DeductionAgent SOLVED) thì bỏ.
    """
    board = puzzle.board
    current_clues = list(puzzle.clues)
    initial_known = {c: puzzle.solution[c] for c in puzzle.initially_revealed}

    # Try removing clues one by one in reverse order
    i = len(current_clues) - 1
    while i >= 0:
        candidate_subset = current_clues[:i] + current_clues[i + 1:]
        # Check uniqueness with candidate subset
        u = check_uniqueness(board, candidate_subset, initial_known)
        if u.is_unique:
            # Check solvability without guessing
            trial_dict = {
                "id": puzzle.id,
                "size": puzzle.size,
                "characters": [c.to_dict() for c in puzzle.characters],
                "solution": {c: s.value for c, s in puzzle.solution.items()},
                "initially_revealed": list(puzzle.initially_revealed),
                "clues": [c.to_dict() for c in candidate_subset],
            }
            run = DeductionAgent().run(FakeEngine(trial_dict))
            if run.outcome is AgentOutcome.SOLVED:
                current_clues = candidate_subset
        i -= 1

    return Puzzle(
        id=puzzle.id,
        size=puzzle.size,
        characters=puzzle.characters,
        solution=puzzle.solution,
        initially_revealed=puzzle.initially_revealed,
        clues=tuple(current_clues),
        difficulty=puzzle.difficulty,
        metadata=puzzle.metadata,
    )


def generate_single_puzzle(
    size: int,
    difficulty: str,
    puzzle_id: str,
    min_ratio: float = 0.30,
    max_ratio: float = 0.50,
    minimize: bool = False,
    rng: Optional[random.Random] = None,
) -> tuple[Puzzle, Any]:
    """Generate one guaranteed valid, no-guess solvable puzzle."""
    if rng is None:
        rng = random.Random()

    chars = generate_characters(size, seed=rng.randint(1, 1_000_000))
    board = Board(size, chars)
    cells = board.cells()
    num_cells = len(cells)

    # 1. Generate hidden solution within ratio
    min_crim = max(1, int(num_cells * min_ratio))
    max_crim = min(num_cells - 1, int(num_cells * max_ratio))
    target_k = rng.randint(min_crim, max_crim)
    crim_cells = set(rng.sample(cells, target_k))
    solution = {c: (Status.CRIMINAL if c in crim_cells else Status.INNOCENT) for c in cells}

    # 2. Pick initially revealed cells
    if size == 3:
        num_init = 2 if difficulty == "EASY" else 1
    elif size == 4:
        num_init = 3 if difficulty == "EASY" else (2 if difficulty == "MEDIUM" else 1)
    else:  # size >= 5
        num_init = 4 if difficulty == "EASY" else (3 if difficulty == "MEDIUM" else 2)

    center_cell = make_cell(size // 2, size // 2)
    initially_revealed = [center_cell]
    other_candidates = [c for c in cells if c != center_cell]
    if num_init > 1:
        initially_revealed.extend(rng.sample(other_candidates, num_init - 1))

    # 3. Constructive deduction loop
    max_attempts = 40
    for attempt in range(max_attempts):
        proved: dict[str, Status] = {c: solution[c] for c in initially_revealed}
        clue_map: dict[str, Clue] = {}

        stuck_counter = 0
        while len(proved) < num_cells and stuck_counter < 50:
            state = PublicState(board, tuple(clue_map.values()), proved)
            kb = build_kb(state)
            forced_cell, forced_status = None, None
            for c in state.unresolved_cells():
                cl_st = classify(kb, c).status
                if cl_st is not None:
                    forced_cell, forced_status = c, cl_st
                    break

            if forced_cell is not None:
                proved[forced_cell] = forced_status
                stuck_counter = 0
                continue

            # Need to force an unproved cell
            unproved = [c for c in cells if c not in proved]
            target = rng.choice(unproved)

            # Pick an owner among proved cells
            available_owners = [c for c in proved if c not in clue_map]
            if available_owners:
                owner = available_owners[0]
            else:
                # If all proved cells already have clues, pick one to strengthen/replace with a direct clue
                owner = rng.choice(list(proved.keys()))

            new_clue = _generate_candidate_clue(
                owner=owner,
                target_cell=target,
                board=board,
                solution=solution,
                proved_cells=set(proved.keys()),
                difficulty=difficulty,
                rng=rng,
                clue_id=f"clue_{owner}",
            )
            # Verify semantic truth
            if semantic_evaluate(new_clue, board, solution):
                clue_map[owner] = new_clue
            stuck_counter += 1

        if len(proved) == num_cells:
            # Fill remaining cards with valid clues
            for c in cells:
                if c not in clue_map:
                    clue_map[c] = _fill_valid_filler_clue(c, board, solution, rng, f"clue_{c}")

            # Assemble puzzle
            clues = tuple(clue_map.values())
            initial_known = {c: solution[c] for c in initially_revealed}

            # Verify uniqueness
            u_res = check_uniqueness(board, clues, initial_known)
            if u_res.is_unique:
                puzzle_data = {
                    "id": puzzle_id,
                    "size": size,
                    "characters": [ch.to_dict() for ch in chars],
                    "solution": {c: s.value for c, s in solution.items()},
                    "initially_revealed": list(initially_revealed),
                    "clues": [cl.to_dict() for cl in clues],
                }
                engine = FakeEngine(puzzle_data)
                run = DeductionAgent().run(engine)
                if run.outcome is AgentOutcome.SOLVED:
                    raw_score, calculated_diff = _score_puzzle(
                        Puzzle.from_dict(puzzle_data), run
                    )
                    puzzle = Puzzle(
                        id=puzzle_id,
                        size=size,
                        characters=tuple(chars),
                        solution=solution,
                        initially_revealed=tuple(initially_revealed),
                        clues=clues,
                        difficulty=difficulty,
                        metadata={
                            "difficulty_score": raw_score,
                            "calculated_difficulty": calculated_diff,
                            "criminal_count": len(crim_cells),
                            "criminal_ratio": round(len(crim_cells) / num_cells, 3),
                            "solve_steps": len(run.steps),
                            "dpll_decisions": run.stats.decisions,
                            "dpll_backtracks": run.stats.backtracks,
                            "dpll_propagations": run.stats.propagations,
                            "dpll_runtime_s": round(run.runtime, 5),
                        },
                    )

                    if minimize:
                        puzzle = minimize_clues(puzzle)

                    return puzzle, run

    raise RuntimeError(f"Failed to generate valid solvable puzzle after {max_attempts} attempts.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Griductive Puzzle Generator & Verifier CLI")
    parser.add_argument("--size", type=int, choices=[3, 4, 5], default=3, help="Grid size (3, 4, 5)")
    parser.add_argument("--count", type=int, default=5, help="Number of puzzles to generate")
    parser.add_argument("--difficulty", choices=["EASY", "MEDIUM", "HARD", "ALL"], default="ALL",
                        help="Difficulty level to generate (default: ALL)")
    parser.add_argument("--min-ratio", type=float, default=0.30, help="Min criminal ratio (default: 0.30)")
    parser.add_argument("--max-ratio", type=float, default=0.50, help="Max criminal ratio (default: 0.50)")
    parser.add_argument("--minimize", action="store_true", help="Minimize clues by removing redundant ones")
    parser.add_argument("--no-cross-check", action="store_true", help="Skip independent cross-checking")
    parser.add_argument("--out-dir", type=str, default=None, help="Output directory for JSON puzzles")
    parser.add_argument("--csv-summary", type=str, default="data/results/puzzles_summary.csv",
                        help="Path to CSV summary file")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")

    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else Path(f"data/puzzles/{args.size}x{args.size}")
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = Path(args.csv_summary)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed) if args.seed is not None else random.Random()
    difficulties = ["EASY", "MEDIUM", "HARD"] if args.difficulty == "ALL" else [args.difficulty]

    print(f"=== Generating {args.count} puzzles for {args.size}x{args.size} board ===")
    print(f"Output directory: {out_dir}")
    print(f"Difficulty mode: {args.difficulty}")
    print(f"Minimize redundant clues: {args.minimize}")
    print(f"Independent Cross-check: {not args.no_cross_check}")

    csv_records = []
    t_start = time.perf_counter()

    for idx in range(1, args.count + 1):
        diff = difficulties[(idx - 1) % len(difficulties)]
        puzzle_id = f"puzzle_{args.size}x{args.size}_{diff.lower()}_{idx:02d}"

        t0 = time.perf_counter()
        puzzle, run = generate_single_puzzle(
            size=args.size,
            difficulty=diff,
            puzzle_id=puzzle_id,
            min_ratio=args.min_ratio,
            max_ratio=args.max_ratio,
            minimize=args.minimize,
            rng=rng,
        )
        gen_time = time.perf_counter() - t0

        # Save JSON
        json_file = out_dir / f"{puzzle_id}.json"
        save_puzzle(puzzle, json_file)

        # Cross check
        cross_check_status = "SKIPPED"
        z3_time = 0.0
        pysat_time = 0.0
        if not args.no_cross_check:
            cc = cross_check_all(puzzle)
            all_ok = all(r.is_unique and r.matches_solution for r in cc.values())
            cross_check_status = "PASS" if all_ok else "FAIL"
            if "z3" in cc:
                z3_time = cc["z3"].runtime_seconds
            if "pysat" in cc:
                pysat_time = cc["pysat"].runtime_seconds

        print(f"  [{idx:02d}/{args.count:02d}] Generated {puzzle_id}: "
              f"diff={puzzle.difficulty}, clues={len(puzzle.clues)}, "
              f"steps={len(run.steps)}, decisions={run.stats.decisions}, "
              f"cross_check={cross_check_status} ({gen_time:.3f}s)")

        meta = puzzle.metadata or {}
        csv_records.append({
            "id": puzzle.id,
            "size": puzzle.size,
            "difficulty": puzzle.difficulty,
            "difficulty_score": meta.get("difficulty_score", 0),
            "num_clues": len(puzzle.clues),
            "criminal_count": meta.get("criminal_count", 0),
            "criminal_ratio": meta.get("criminal_ratio", 0),
            "initially_revealed": " ".join(puzzle.initially_revealed),
            "solve_steps": len(run.steps),
            "dpll_decisions": run.stats.decisions,
            "dpll_backtracks": run.stats.backtracks,
            "dpll_propagations": run.stats.propagations,
            "dpll_runtime_s": meta.get("dpll_runtime_s", 0),
            "z3_runtime_s": round(z3_time, 5),
            "pysat_runtime_s": round(pysat_time, 5),
            "cross_check_status": cross_check_status,
        })

    # Write / append CSV
    fieldnames = [
        "id", "size", "difficulty", "difficulty_score", "num_clues",
        "criminal_count", "criminal_ratio", "initially_revealed", "solve_steps",
        "dpll_decisions", "dpll_backtracks", "dpll_propagations",
        "dpll_runtime_s", "z3_runtime_s", "pysat_runtime_s", "cross_check_status"
    ]
    file_exists = csv_path.exists() and csv_path.stat().st_size > 0
    with open(csv_path, "a" if file_exists else "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for r in csv_records:
            writer.writerow(r)

    total_time = time.perf_counter() - t_start
    print(f"\nSuccessfully generated {len(csv_records)} puzzles in {total_time:.2f}s.")
    print(f"Summary written to: {csv_path}")


if __name__ == "__main__":
    main()
