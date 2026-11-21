"""[E] Create deterministic edge / failure / stress cases for Section 4.5 & 4.6 evaluation.

Stored in ``data/edge_cases/`` (separate from playable ``data/puzzles/``) so the GUI
stage list stays 100% valid while experiments explicitly measure and report:
  1. STUCK (ambiguous / missing clues -> MULTIPLE solutions)
  2. INCONSISTENT (contradictory clues -> NO_SOLUTION)
  3. STRESS (extension-heavy 5x5 -> SOLVED / TIMEOUT / STEP_LIMIT)
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from algorithms.agent.deduction_agent import AgentOutcome, DeductionAgent
from algorithms.agent.uniqueness import Uniqueness, check_uniqueness
from algorithms.logic.models import Board, Clue, ClueType, Status
from algorithms.tests.helpers import FakeEngine
from data.puzzle_loader import Puzzle, load_puzzle, save_puzzle
from data.scripts.generate_puzzles import generate_single_puzzle
from data.scripts.names_pool import generate_characters


def build_edge_cases(out_dir: Path, puzzles_dir: Path = Path("data/puzzles")) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []

    # 1. 3x3 STUCK: missing clues -> multiple solutions, agent refuses to guess
    chars_3 = tuple(generate_characters(3, seed=11))
    board_3 = Board(3, chars_3)
    sol_3 = {c: (Status.CRIMINAL if c in ("A1", "C2", "B3") else Status.INNOCENT) for c in board_3.cells()}
    clues_stuck_3 = (
        Clue("clue_B2", "B2", ClueType.EXACTLY, {"region": {"kind": "row", "row": 1}, "k": 1}),
        Clue("clue_A1", "A1", ClueType.PARITY, {"region": {"kind": "col", "col": "C"}, "parity": "ODD"}),
    )
    pz_stuck_3 = Puzzle(
        id="case_3x3_stuck_missing_clues",
        size=3,
        characters=chars_3,
        solution=sol_3,
        initially_revealed=("B2",),
        clues=clues_stuck_3,
        difficulty="EDGE_STUCK",
        metadata={"edge_type": "STUCK", "reason": "Insufficient clues (7 cells remain ambiguous)"},
    )
    p1 = out_dir / "case_3x3_stuck_missing_clues.json"
    save_puzzle(pz_stuck_3, p1)
    created.append(p1)

    # 2. 4x4 STUCK: partial deduction then stuck mid-game
    base_4x4 = load_puzzle(puzzles_dir / "4x4" / "puzzle_4x4_medium_02.json")
    kept_owners = set(base_4x4.initially_revealed) | {"A1", "B1", "A2", "B2", "C2"}
    clues_stuck_4 = tuple(cl for cl in base_4x4.clues if cl.owner in kept_owners)
    pz_stuck_4 = Puzzle(
        id="case_4x4_stuck_ambiguous",
        size=4,
        characters=base_4x4.characters,
        solution=base_4x4.solution,
        initially_revealed=base_4x4.initially_revealed,
        clues=clues_stuck_4,
        difficulty="EDGE_STUCK",
        metadata={"edge_type": "STUCK", "reason": "Partial clues solve initial wave then become ambiguous"},
    )
    p2 = out_dir / "case_4x4_stuck_ambiguous.json"
    save_puzzle(pz_stuck_4, p2)
    created.append(p2)

    # 3. 3x3 INCONSISTENT: direct conflict SAME vs DIFFERENT
    sol_inc_3 = {c: (Status.CRIMINAL if c in ("A1", "B1", "C3") else Status.INNOCENT) for c in board_3.cells()}
    clues_inc_3 = (
        Clue("clue_A1", "A1", ClueType.SAME, {"a": chars_3[0].name, "b": chars_3[1].name}),
        Clue("clue_B1", "B1", ClueType.DIFFERENT, {"a": chars_3[0].name, "b": chars_3[1].name}),
        Clue("clue_C1", "C1", ClueType.EXACTLY, {"region": {"kind": "row", "row": 1}, "k": 2}),
    )
    pz_inc_3 = Puzzle(
        id="case_3x3_inconsistent_conflict",
        size=3,
        characters=chars_3,
        solution=sol_inc_3,
        initially_revealed=("A1", "B1"),
        clues=clues_inc_3,
        difficulty="EDGE_INCONSISTENT",
        metadata={"edge_type": "INCONSISTENT", "reason": "Direct contradiction: SAME(A1,B1) vs DIFFERENT(A1,B1)"},
    )
    p3 = out_dir / "case_3x3_inconsistent_conflict.json"
    save_puzzle(pz_inc_3, p3)
    created.append(p3)

    # 4. 4x4 INCONSISTENT: cardinality vs parity conflict (EXACTLY 2 vs PARITY ODD on row 1)
    chars_4 = tuple(generate_characters(4, seed=22))
    board_4 = Board(4, chars_4)
    sol_inc_4 = {c: (Status.CRIMINAL if c in ("A1", "B1", "C3", "D4") else Status.INNOCENT) for c in board_4.cells()}
    clues_inc_4 = (
        Clue("clue_A1", "A1", ClueType.EXACTLY, {"region": {"kind": "row", "row": 1}, "k": 2}),
        Clue("clue_B1", "B1", ClueType.PARITY, {"region": {"kind": "row", "row": 1}, "parity": "ODD"}),
        Clue("clue_C1", "C1", ClueType.AT_LEAST, {"region": {"kind": "col", "col": "C"}, "k": 1}),
    )
    pz_inc_4 = Puzzle(
        id="case_4x4_inconsistent_cardinality",
        size=4,
        characters=chars_4,
        solution=sol_inc_4,
        initially_revealed=("A1", "B1"),
        clues=clues_inc_4,
        difficulty="EDGE_INCONSISTENT",
        metadata={"edge_type": "INCONSISTENT", "reason": "EXACTLY 2 vs PARITY ODD on row 1"},
    )
    p4 = out_dir / "case_4x4_inconsistent_cardinality.json"
    save_puzzle(pz_inc_4, p4)
    created.append(p4)

    # 5. 5x5 STRESS: extension-heavy 5x5 with non-zero DPLL decisions for stress/timeout/step_limit tests
    best_stress: Puzzle | None = None
    best_score = -1
    for seed in (2026, 2027, 2028, 2029, 2030, 2031):
        pz, run = generate_single_puzzle(
            size=5,
            difficulty="HARD",
            puzzle_id="case_5x5_stress_extensions",
            require_extensions=True,
            rng=random.Random(seed),
        )
        score = run.max_aux_vars * 2 + run.stats.decisions * 10 + run.max_clauses
        if run.stats.decisions > 0 and run.max_aux_vars > 0 and score > best_score:
            best_stress = pz
            best_score = score
            if run.stats.decisions >= 5 and run.max_aux_vars >= 15:
                break
    if best_stress is None:
        best_stress, _ = generate_single_puzzle(
            size=5,
            difficulty="HARD",
            puzzle_id="case_5x5_stress_extensions",
            require_extensions=True,
            rng=random.Random(2026),
        )
    p5 = out_dir / "case_5x5_stress_extensions.json"
    save_puzzle(best_stress, p5)
    created.append(p5)

    return created


def verify_edge_cases(edge_dir: Path) -> None:
    expected = {
        "case_3x3_stuck_missing_clues": (AgentOutcome.STUCK, Uniqueness.MULTIPLE),
        "case_4x4_stuck_ambiguous": (AgentOutcome.STUCK, Uniqueness.MULTIPLE),
        "case_3x3_inconsistent_conflict": (AgentOutcome.INCONSISTENT, Uniqueness.NO_SOLUTION),
        "case_4x4_inconsistent_cardinality": (AgentOutcome.INCONSISTENT, Uniqueness.NO_SOLUTION),
        "case_5x5_stress_extensions": (AgentOutcome.SOLVED, Uniqueness.UNIQUE),
    }
    for path in sorted(edge_dir.glob("*.json")):
        pz = load_puzzle(path)
        known = {c: pz.solution[c] for c in pz.initially_revealed}
        u = check_uniqueness(pz.board, pz.clues, known)
        run = DeductionAgent(time_limit=30.0).run(FakeEngine(pz.to_dict()))
        exp_out, exp_uniq = expected[pz.id]
        assert run.outcome is exp_out, f"{pz.id}: expected {exp_out}, got {run.outcome}"
        assert u.status is exp_uniq, f"{pz.id}: expected {exp_uniq}, got {u.status}"
        print(f"Verified {pz.id:<36} -> outcome={run.outcome.value:<12} uniqueness={u.status.value} "
              f"steps={len(run.steps)} aux={run.max_aux_vars} decisions={run.stats.decisions}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create edge/failure cases in data/edge_cases/")
    parser.add_argument("--out-dir", type=str, default="data/edge_cases", help="Output directory")
    parser.add_argument("--puzzles-dir", type=str, default="data/puzzles", help="Base puzzles directory")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    created = build_edge_cases(out_dir, Path(args.puzzles_dir))
    print(f"Created {len(created)} edge-case JSON files in {out_dir}:")
    verify_edge_cases(out_dir)


if __name__ == "__main__":
    main()
