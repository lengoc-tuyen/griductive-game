"""[E] Puzzle Generator CLI Script.

Generates valid, no-guess solvable, uniquely satisfiable Griductive puzzles
for 3x3, 4x4, and 5x5 boards, with independent cross-checking, advanced regions,
multi-cell extension clues, duplicate-clue prevention, and difficulty rating.
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from algorithms.agent.deduction_agent import AgentOutcome, DeductionAgent
from algorithms.agent.entailment import classify
from algorithms.agent.knowledge_base import build_kb
from algorithms.agent.public_state import PublicState
from algorithms.agent.uniqueness import check_uniqueness
from algorithms.logic.clues import validate as validate_clue
from algorithms.logic.errors import ClueValidationError
from algorithms.logic.evaluator import evaluate as semantic_evaluate
from algorithms.logic.models import Board, Clue, ClueType, Status, make_cell, parse_cell
from algorithms.logic.regions import RegionError, clue_region, neighbors_of, resolve as resolve_region
from algorithms.tests.helpers import FakeEngine
from data.puzzle_loader import Puzzle, save_puzzle
from data.scripts.cross_checker import cross_check_all
from data.scripts.names_pool import generate_characters


def _count_criminals(solution: Mapping[str, Status], cells: Sequence[str], count_innocent: bool = False) -> int:
    target = Status.INNOCENT if count_innocent else Status.CRIMINAL
    return sum(1 for c in cells if solution[c] is target)


def clue_signature(clue: Clue, board: Board) -> tuple[Any, ...]:
    """Canonical semantic signature used to prevent duplicate clues inside a puzzle."""
    p = clue.params
    t = clue.type
    if t is ClueType.FACT:
        return ("FACT", board.cell_of(p["person"]), Status(p["status"]).value)
    if t in (ClueType.SAME, ClueType.DIFFERENT):
        pair = tuple(sorted((board.cell_of(p["a"]), board.cell_of(p["b"]))))
        return (t.value, pair)
    if t in (ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST):
        cells = tuple(clue_region(clue, board))
        return (t.value, cells, clue.counted_status.value, int(p["k"]))
    if t is ClueType.PARITY:
        cells = tuple(clue_region(clue, board))
        return ("PARITY", cells, clue.counted_status.value, p["parity"])
    if t is ClueType.COMPARE:
        a = tuple(clue_region(clue, board, "region_a"))
        b = tuple(clue_region(clue, board, "region_b"))
        op = p["op"]
        if op == "FEWER":
            return ("COMPARE", "MORE", b, a, clue.counted_status.value)
        if op == "EQUAL":
            first, second = sorted((a, b))
            return ("COMPARE", "EQUAL", first, second, clue.counted_status.value)
        return ("COMPARE", "MORE", a, b, clue.counted_status.value)
    return (t.value, str(sorted(p.items())))


def _advanced_region_candidates(
    target_cell: Optional[str],
    board: Board,
    proved_cells: set[str],
    rng: random.Random,
    strict_proved: bool = True,
    max_unproved: int = 2,
) -> list[dict[str, Any]]:
    """Build valid advanced region specs (corners, edges, between, common_neighbors)."""
    specs: list[dict[str, Any]] = []
    cells = board.cells()

    def _keep(reg_cells: list[str]) -> bool:
        if not reg_cells:
            return False
        if target_cell is not None and target_cell not in reg_cells:
            return False
        if strict_proved:
            return sum(1 for c in reg_cells if c not in proved_cells) <= max_unproved
        return True

    # 1. corners & edges
    for kind in ("corners", "edges"):
        spec = {"kind": kind}
        reg_cells = resolve_region(spec, board)
        if _keep(reg_cells):
            specs.append(spec)

    # 2. between (two collinear cells with at least 1 cell strictly between them)
    between_specs: list[dict[str, Any]] = []
    if target_cell is not None:
        tc, tr = parse_cell(target_cell)
        row_pairs = [
            (make_cell(c1, tr), make_cell(c2, tr))
            for c1 in range(tc) for c2 in range(tc + 1, board.size)
        ]
        col_pairs = [
            (make_cell(tc, r1), make_cell(tc, r2))
            for r1 in range(tr) for r2 in range(tr + 1, board.size)
        ]
        candidate_pairs = row_pairs + col_pairs
    else:
        candidate_pairs = []
        for r in range(board.size):
            for c1 in range(board.size):
                for c2 in range(c1 + 2, board.size):
                    candidate_pairs.append((make_cell(c1, r), make_cell(c2, r)))
        for c in range(board.size):
            for r1 in range(board.size):
                for r2 in range(r1 + 2, board.size):
                    candidate_pairs.append((make_cell(c, r1), make_cell(c, r2)))

    rng.shuffle(candidate_pairs)
    for ca, cb in candidate_pairs:
        na = board.character_at(ca).name
        nb = board.character_at(cb).name
        spec = {"kind": "between", "a": na, "b": nb}
        reg_cells = resolve_region(spec, board)
        if _keep(reg_cells):
            between_specs.append(spec)
            if len(between_specs) >= 3:
                break
    specs.extend(between_specs)

    # 3. common_neighbors (pairs sharing >= 2 neighbors)
    common_specs: list[dict[str, Any]] = []
    if target_cell is not None:
        nbrs = neighbors_of(target_cell, board)
        pair_list = [(nbrs[i], nbrs[j]) for i in range(len(nbrs)) for j in range(i + 1, len(nbrs))]
    else:
        pair_list = [(cells[i], cells[j]) for i in range(len(cells)) for j in range(i + 1, len(cells))]
    rng.shuffle(pair_list)
    for ca, cb in pair_list:
        na = board.character_at(ca).name
        nb = board.character_at(cb).name
        spec = {"kind": "common_neighbors", "a": na, "b": nb}
        try:
            reg_cells = resolve_region(spec, board)
        except RegionError:
            continue
        if len(reg_cells) >= 2 and _keep(reg_cells):
            common_specs.append(spec)
            if len(common_specs) >= 3:
                break
    specs.extend(common_specs)

    return specs


def _basic_region_candidates(
    target_cell: str,
    board: Board,
    proved_cells: set[str],
    owner: str,
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Build standard region candidates (row, col, cells, neighbors) centered on target_cell."""
    c_idx, r_idx = parse_cell(target_cell)
    row_cells = [make_cell(c, r_idx) for c in range(board.size)]
    col_cells = [make_cell(c_idx, r) for r in range(board.size)]

    region_options: list[dict[str, Any]] = []
    if all(c in proved_cells for c in row_cells if c != target_cell):
        region_options.append({"kind": "row", "row": r_idx + 1})
    if all(c in proved_cells for c in col_cells if c != target_cell):
        region_options.append({"kind": "col", "col": chr(ord("A") + c_idx)})

    if proved_cells:
        ref_proved = [owner] if (owner in proved_cells and owner != target_cell) else []
        other_proved = [p for p in proved_cells if p != target_cell and p != owner]
        if other_proved:
            ref_proved.append(rng.choice(other_proved))
        if not ref_proved:
            ref_proved = [rng.choice(list(proved_cells))]
        subset = sorted(set(ref_proved + [target_cell]))
        if len(subset) >= 2:
            region_options.append({"kind": "cells", "cells": subset})

    for p in proved_cells:
        nb = neighbors_of(p, board)
        if target_cell in nb and sum(1 for n in nb if n not in proved_cells) <= 2:
            region_options.append({"kind": "neighbors", "of": p})
            break

    if not region_options:
        fallback = sorted({owner, target_cell})
        if len(fallback) < 2:
            others = [c for c in board.cells() if c != target_cell]
            fallback = sorted([target_cell, rng.choice(others)])
        region_options.append({"kind": "cells", "cells": fallback})

    return region_options


def _all_region_pool(board: Board, rng: random.Random) -> list[dict[str, Any]]:
    """Diverse region pool of size >= 2 for COMPARE region_b or filler clues."""
    pool: list[dict[str, Any]] = []
    for r in range(1, board.size + 1):
        pool.append({"kind": "row", "row": r})
    for c in range(board.size):
        pool.append({"kind": "col", "col": chr(ord("A") + c)})
    pool.append({"kind": "corners"})
    pool.append({"kind": "edges"})
    sample_cells = rng.sample(board.cells(), min(4, board.size * board.size))
    for sc in sample_cells:
        pool.append({"kind": "neighbors", "of": sc})
    pool.extend(_advanced_region_candidates(None, board, set(), rng, strict_proved=False))
    return pool


def _build_compare_clue(
    owner: str,
    board: Board,
    solution: Mapping[str, Status],
    reg_a: dict[str, Any],
    reg_b: dict[str, Any],
    counts_innocent: bool,
    clue_id: str,
) -> Optional[Clue]:
    cells_a = resolve_region(reg_a, board)
    cells_b = resolve_region(reg_b, board)
    if len(cells_a) < 2 or len(cells_b) < 2 or set(cells_a) == set(cells_b):
        return None
    cnt_a = _count_criminals(solution, cells_a, counts_innocent)
    cnt_b = _count_criminals(solution, cells_b, counts_innocent)
    op = "EQUAL" if cnt_a == cnt_b else ("MORE" if cnt_a > cnt_b else "FEWER")
    params: dict[str, Any] = {"region_a": reg_a, "region_b": reg_b, "op": op}
    if counts_innocent:
        params["counts"] = "INNOCENT"
    clue = Clue(clue_id, owner, ClueType.COMPARE, params)
    try:
        validate_clue(clue, board)
    except ClueValidationError:
        return None
    return clue


def _generate_candidate_clue(
    owner: str,
    target_cell: str,
    board: Board,
    solution: Mapping[str, Status],
    proved_cells: set[str],
    difficulty: str,
    rng: random.Random,
    clue_id: str,
    existing_sigs: Optional[set[tuple[Any, ...]]] = None,
) -> Clue:
    """Generate a valid clue owned by `owner` that constrains `target_cell` without duplicating."""
    target_status = solution[target_cell]
    target_name = board.character_at(target_cell).name

    if difficulty == "EASY":
        types = [ClueType.FACT, ClueType.SAME, ClueType.DIFFERENT, ClueType.EXACTLY]
        weights = [0.30, 0.30, 0.20, 0.20]
    elif difficulty == "MEDIUM":
        types = [ClueType.SAME, ClueType.DIFFERENT, ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST, ClueType.PARITY]
        weights = [0.18, 0.18, 0.28, 0.14, 0.14, 0.08]
    else:  # HARD
        types = [ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST, ClueType.PARITY, ClueType.COMPARE, ClueType.SAME]
        weights = [0.22, 0.15, 0.15, 0.22, 0.18, 0.08]

    for _attempt in range(14):
        chosen_type = rng.choices(types, weights=weights, k=1)[0]
        counts_innocent = (difficulty == "HARD" and rng.random() < 0.30) or (
            difficulty == "MEDIUM" and rng.random() < 0.10
        )

        candidate: Optional[Clue] = None

        if chosen_type is ClueType.FACT:
            candidate = Clue(
                id=clue_id,
                owner=owner,
                type=ClueType.FACT,
                params={"person": target_name, "status": target_status.value},
            )

        elif chosen_type in (ClueType.SAME, ClueType.DIFFERENT):
            ref_cell = owner if (owner in proved_cells and owner != target_cell) else (
                rng.choice([c for c in proved_cells if c != target_cell])
                if any(c != target_cell for c in proved_cells)
                else rng.choice([c for c in board.cells() if c != target_cell])
            )
            ref_name = board.character_at(ref_cell).name
            same = (solution[target_cell] == solution[ref_cell])
            actual_type = ClueType.SAME if same else ClueType.DIFFERENT
            candidate = Clue(
                id=clue_id,
                owner=owner,
                type=actual_type,
                params={"a": target_name, "b": ref_name},
            )

        elif chosen_type in (ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST, ClueType.PARITY):
            basic_opts = _basic_region_candidates(target_cell, board, proved_cells, owner, rng)
            adv_opts = (
                _advanced_region_candidates(target_cell, board, proved_cells, rng, strict_proved=True, max_unproved=2)
                if difficulty in ("MEDIUM", "HARD")
                else []
            )
            if adv_opts and (difficulty == "HARD" and rng.random() < 0.65 or rng.random() < 0.35):
                region_spec = rng.choice(adv_opts)
            else:
                region_spec = rng.choice(basic_opts + adv_opts)

            reg_cells = resolve_region(region_spec, board)
            k_actual = _count_criminals(solution, reg_cells, count_innocent=counts_innocent)

            params: dict[str, Any] = {"region": region_spec}
            if counts_innocent:
                params["counts"] = "INNOCENT"

            if chosen_type is ClueType.EXACTLY:
                params["k"] = k_actual
                candidate = Clue(clue_id, owner, ClueType.EXACTLY, params)
            elif chosen_type is ClueType.AT_LEAST:
                params["k"] = k_actual
                candidate = Clue(clue_id, owner, ClueType.AT_LEAST, params)
            elif chosen_type is ClueType.AT_MOST:
                params["k"] = k_actual
                candidate = Clue(clue_id, owner, ClueType.AT_MOST, params)
            else:  # PARITY
                if reg_cells:
                    params["parity"] = "ODD" if k_actual % 2 == 1 else "EVEN"
                    candidate = Clue(clue_id, owner, ClueType.PARITY, params)

        elif chosen_type is ClueType.COMPARE:
            basic_opts = _basic_region_candidates(target_cell, board, proved_cells, owner, rng)
            adv_opts = _advanced_region_candidates(
                target_cell, board, proved_cells, rng, strict_proved=True, max_unproved=2
            )
            pool_a = [r for r in (adv_opts + basic_opts) if len(resolve_region(r, board)) >= 2]
            if not pool_a:
                others = [c for c in board.cells() if c != target_cell]
                partner = rng.choice(list(proved_cells - {target_cell}) or others)
                pool_a = [{"kind": "cells", "cells": sorted([target_cell, partner])}]
            reg_a = rng.choice(pool_a)
            cells_a = set(resolve_region(reg_a, board))

            # Prefer a proved-heavy region B so COMPARE propagates cleanly onto target_cell
            pool_b: list[dict[str, Any]] = []
            for r_spec in _all_region_pool(board, rng):
                try:
                    c_b = resolve_region(r_spec, board)
                except RegionError:
                    continue
                if len(c_b) >= 2 and set(c_b) != cells_a:
                    pool_b.append(r_spec)
            if len(proved_cells) >= 2:
                proved_sample = sorted(rng.sample(list(proved_cells), min(3, len(proved_cells))))
                if set(proved_sample) != cells_a:
                    pool_b.insert(0, {"kind": "cells", "cells": proved_sample})
            # Rank pool_b to favor mostly-proved regions
            pool_b.sort(key=lambda r: sum(1 for c in resolve_region(r, board) if c not in proved_cells))
            if pool_b:
                top_b = pool_b[: max(1, min(4, len(pool_b)))]
                reg_b = rng.choice(top_b)
                candidate = _build_compare_clue(owner, board, solution, reg_a, reg_b, counts_innocent, clue_id)

        if candidate is None:
            continue
        try:
            validate_clue(candidate, board)
        except ClueValidationError:
            continue
        if existing_sigs is not None and clue_signature(candidate, board) in existing_sigs:
            continue
        return candidate

    return _fill_valid_filler_clue(owner, board, solution, rng, clue_id, difficulty=difficulty, existing_sigs=existing_sigs)


def _fill_valid_filler_clue(
    owner: str,
    board: Board,
    solution: Mapping[str, Status],
    rng: random.Random,
    clue_id: str,
    difficulty: str = "MEDIUM",
    existing_sigs: Optional[set[tuple[Any, ...]]] = None,
) -> Clue:
    """Generate any semantically true, non-duplicate clue for card `owner`."""
    c_idx, r_idx = parse_cell(owner)
    all_cells = board.cells()
    sigs = existing_sigs or set()

    region_pool: list[dict[str, Any]] = [
        {"kind": "row", "row": r_idx + 1},
        {"kind": "col", "col": chr(ord("A") + c_idx)},
        {"kind": "neighbors", "of": owner},
    ]
    if difficulty in ("MEDIUM", "HARD"):
        region_pool.extend(_advanced_region_candidates(None, board, set(), rng, strict_proved=False))

    # Add explicit cell subsets around owner
    others = [c for c in all_cells if c != owner]
    for _ in range(4):
        sub = sorted([owner] + rng.sample(others, min(2, len(others))))
        region_pool.append({"kind": "cells", "cells": sub})

    candidates: list[Clue] = []
    # For HARD puzzles, include multi-cell COMPARE and PARITY candidates upfront
    if difficulty == "HARD":
        multi_regs = [r for r in _all_region_pool(board, rng) if len(resolve_region(r, board)) >= 2]
        rng.shuffle(multi_regs)
        for i in range(min(5, len(multi_regs) - 1)):
            c_inn = rng.random() < 0.30
            cmp_clue = _build_compare_clue(owner, board, solution, multi_regs[i], multi_regs[i + 1], c_inn, clue_id)
            if cmp_clue is not None:
                candidates.append(cmp_clue)

    rng.shuffle(region_pool)
    for reg in region_pool:
        try:
            reg_cells = resolve_region(reg, board)
        except RegionError:
            continue
        if not reg_cells:
            continue
        c_inn = difficulty == "HARD" and rng.random() < 0.30
        k_val = _count_criminals(solution, reg_cells, count_innocent=c_inn)
        base_params: dict[str, Any] = {"region": reg}
        if c_inn:
            base_params["counts"] = "INNOCENT"

        if difficulty in ("MEDIUM", "HARD"):
            p_params = dict(base_params, parity="ODD" if k_val % 2 == 1 else "EVEN")
            candidates.append(Clue(clue_id, owner, ClueType.PARITY, p_params))

        candidates.append(Clue(clue_id, owner, ClueType.EXACTLY, dict(base_params, k=k_val)))
        if k_val > 0:
            candidates.append(Clue(clue_id, owner, ClueType.AT_LEAST, dict(base_params, k=k_val)))
        if k_val < len(reg_cells):
            candidates.append(Clue(clue_id, owner, ClueType.AT_MOST, dict(base_params, k=k_val)))

    # Fallback pairwise SAME / DIFFERENT and FACT
    rng.shuffle(others)
    for other in others[:6]:
        n1 = board.character_at(owner).name
        n2 = board.character_at(other).name
        ctype = ClueType.SAME if solution[owner] is solution[other] else ClueType.DIFFERENT
        candidates.append(Clue(clue_id, owner, ctype, {"a": n1, "b": n2}))
    for cell in rng.sample(all_cells, min(len(all_cells), 6)):
        candidates.append(Clue(clue_id, owner, ClueType.FACT, {
            "person": board.character_at(cell).name,
            "status": solution[cell].value,
        }))

    # Prioritize extension clues slightly when difficulty is HARD without losing randomness
    if difficulty == "HARD":
        ext = [c for c in candidates if c.type in (ClueType.PARITY, ClueType.COMPARE)]
        non_ext = [c for c in candidates if c.type not in (ClueType.PARITY, ClueType.COMPARE)]
        rng.shuffle(ext)
        rng.shuffle(non_ext)
        ordered = ext[:3] + non_ext + ext[3:]
    else:
        ordered = candidates
        rng.shuffle(ordered)

    for cand in ordered:
        try:
            validate_clue(cand, board)
        except ClueValidationError:
            continue
        if not semantic_evaluate(cand, board, solution):
            continue
        if clue_signature(cand, board) in sigs:
            continue
        return cand

    # Absolute fallback (different cell FACT)
    for cell in all_cells:
        cand = Clue(clue_id, owner, ClueType.FACT, {
            "person": board.character_at(cell).name,
            "status": solution[cell].value,
        })
        if clue_signature(cand, board) not in sigs:
            return cand
    return Clue(clue_id, owner, ClueType.FACT, {
        "person": board.character_at(owner).name,
        "status": solution[owner].value,
    })


def _score_puzzle(puzzle: Puzzle, run: Any) -> tuple[float, str]:
    """Compute difficulty score and classification."""
    steps = len(run.steps)
    decisions = run.stats.decisions
    backtracks = run.stats.backtracks

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
    """Drop redundant clues while preserving uniqueness and no-guess solvability."""
    board = puzzle.board
    current_clues = list(puzzle.clues)
    initial_known = {c: puzzle.solution[c] for c in puzzle.initially_revealed}

    i = len(current_clues) - 1
    while i >= 0:
        candidate_subset = current_clues[:i] + current_clues[i + 1:]
        u = check_uniqueness(board, candidate_subset, initial_known)
        if u.is_unique:
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
    require_extensions: bool = False,
    rng: Optional[random.Random] = None,
) -> tuple[Puzzle, Any]:
    """Generate one guaranteed valid, no-guess solvable, duplicate-free puzzle."""
    if rng is None:
        rng = random.Random()

    chars = generate_characters(size, seed=rng.randint(1, 1_000_000))
    board = Board(size, chars)
    cells = board.cells()
    num_cells = len(cells)

    min_crim = max(1, int(num_cells * min_ratio))
    max_crim = min(num_cells - 1, int(num_cells * max_ratio))
    target_k = rng.randint(min_crim, max_crim)
    crim_cells = set(rng.sample(cells, target_k))
    solution = {c: (Status.CRIMINAL if c in crim_cells else Status.INNOCENT) for c in cells}

    if size == 3:
        num_init = 2 if difficulty == "EASY" else 1
    elif size == 4:
        num_init = 3 if difficulty == "EASY" else (2 if difficulty == "MEDIUM" else 1)
    else:
        num_init = 4 if difficulty == "EASY" else (3 if difficulty == "MEDIUM" else 2)

    center_cell = make_cell(size // 2, size // 2)
    initially_revealed = [center_cell]
    other_candidates = [c for c in cells if c != center_cell]
    if num_init > 1:
        initially_revealed.extend(rng.sample(other_candidates, num_init - 1))

    max_attempts = 40
    for _attempt in range(max_attempts):
        proved: dict[str, Status] = {c: solution[c] for c in initially_revealed}
        clue_map: dict[str, Clue] = {}
        existing_sigs: set[tuple[Any, ...]] = set()

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

            unproved = [c for c in cells if c not in proved]
            target = rng.choice(unproved)

            available_owners = [c for c in proved if c not in clue_map]
            owner = available_owners[0] if available_owners else rng.choice(list(proved.keys()))

            # Exclude previous owner clue's signature when replacing
            other_sigs = {
                clue_signature(cl, board) for own, cl in clue_map.items() if own != owner
            }
            new_clue = _generate_candidate_clue(
                owner=owner,
                target_cell=target,
                board=board,
                solution=solution,
                proved_cells=set(proved.keys()),
                difficulty=difficulty,
                rng=rng,
                clue_id=f"clue_{owner}",
                existing_sigs=other_sigs,
            )
            sig = clue_signature(new_clue, board)
            if semantic_evaluate(new_clue, board, solution) and sig not in other_sigs:
                clue_map[owner] = new_clue
                existing_sigs = {clue_signature(cl, board) for cl in clue_map.values()}
            stuck_counter += 1

        if len(proved) == num_cells:
            existing_sigs = {clue_signature(cl, board) for cl in clue_map.values()}
            for c in cells:
                if c not in clue_map:
                    filler = _fill_valid_filler_clue(
                        c, board, solution, rng, f"clue_{c}", difficulty=difficulty, existing_sigs=existing_sigs
                    )
                    clue_map[c] = filler
                    existing_sigs.add(clue_signature(filler, board))

            clues = tuple(clue_map[c] for c in cells)
            if require_extensions and not any(cl.type in (ClueType.PARITY, ClueType.COMPARE) for cl in clues):
                continue

            initial_known = {c: solution[c] for c in initially_revealed}
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
                    raw_score, calculated_diff = _score_puzzle(Puzzle.from_dict(puzzle_data), run)
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
    parser.add_argument("--require-extensions", action="store_true",
                        help="Require at least one PARITY/COMPARE clue (aux_vars > 0)")
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
            require_extensions=args.require_extensions,
            rng=rng,
        )
        gen_time = time.perf_counter() - t0

        json_file = out_dir / f"{puzzle_id}.json"
        save_puzzle(puzzle, json_file)

        cross_check_status = "SKIPPED"
        z3_time = 0.0
        pysat_time = 0.0
        if not args.no_cross_check:
            cc = cross_check_all(puzzle)
            ran = [r for r in cc.values() if r.available]
            if not ran:
                cross_check_status = "SKIPPED"
            elif all(r.is_unique and r.matches_solution for r in ran):
                cross_check_status = "PASS"
            else:
                cross_check_status = "FAIL"
            if "z3" in cc and cc["z3"].available:
                z3_time = cc["z3"].runtime_seconds
            if "pysat" in cc and cc["pysat"].available:
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
