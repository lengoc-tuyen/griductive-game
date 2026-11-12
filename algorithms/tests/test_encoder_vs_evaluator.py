"""[A] Cross-test: for every complete assignment, CNF(clue) must agree with the evaluator.

For a clue with auxiliary variables, "CNF is true under an assignment of the primary
variables" means: CNF AND (unit clause per primary variable) is satisfiable, i.e. some
values of the auxiliary variables complete it.
"""

import itertools
import random
import unittest

from algorithms.logic import regions
from algorithms.logic.encoder import CNFEncoder
from algorithms.logic.evaluator import evaluate, violated
from algorithms.logic.models import Board, Character, Clue, ClueType, Status
from algorithms.sat.dpll import DPLLSolver
from algorithms.tests.helpers import load_fixture

REGIONS_3 = [
    {"kind": "row", "row": 1}, {"kind": "row", "row": 3}, {"kind": "col", "col": "A"},
    {"kind": "col", "col": "C"}, {"kind": "neighbors", "of": "B2"}, {"kind": "neighbors", "of": "A1"},
    {"kind": "cells", "cells": ["A1", "C3", "B2"]}, {"kind": "corners"}, {"kind": "edges"},
    {"kind": "between", "a": "A1", "b": "C1"}, {"kind": "common_neighbors", "a": "A1", "b": "C1"},
]


def all_clues_3x3(board: Board):
    """A systematic sample: every core type, both counted statuses, both extensions."""
    out = [
        Clue("f1", "A1", ClueType.FACT, {"person": "Alice", "status": "CRIMINAL"}),
        Clue("f2", "A1", ClueType.FACT, {"person": "Ivy", "status": "INNOCENT"}),
        Clue("s1", "A1", ClueType.SAME, {"a": "Alice", "b": "Ivy"}),
        Clue("d1", "A1", ClueType.DIFFERENT, {"a": "Bob", "b": "Eve"}),
    ]
    for r, region in enumerate(REGIONS_3):
        size = len(regions.resolve(region, board))
        for counts in ("CRIMINAL", "INNOCENT"):
            for t in (ClueType.EXACTLY, ClueType.AT_LEAST, ClueType.AT_MOST):
                for k in sorted({0, 1, size // 2, size}):
                    out.append(Clue(f"{t.value}{r}{counts[0]}{k}", "A1", t,
                                    {"region": region, "k": k, "counts": counts}))
            for parity in ("ODD", "EVEN"):
                out.append(Clue(f"P{r}{counts[0]}{parity}", "A1", ClueType.PARITY,
                                {"region": region, "parity": parity, "counts": counts}))
    pairs = [(0, 2), (4, 6), (7, 8), (1, 9), (3, 10)]
    for a, b in pairs:
        for op in ("MORE", "FEWER", "EQUAL"):
            out.append(Clue(f"C{a}{b}{op}", "A1", ClueType.COMPARE,
                            {"region_a": REGIONS_3[a], "region_b": REGIONS_3[b], "op": op}))
    return out


def cnf_holds(solver: DPLLSolver, var_of, assignment) -> bool:
    return solver.solve([v if assignment[c] else -v for c, v in var_of.items()]).is_sat


class TestEncoderVsEvaluator(unittest.TestCase):
    def check_board(self, board: Board, clues, assignments):
        for clue in clues:
            enc = CNFEncoder(board)
            clauses = enc.encode_clue(clue)
            solver = DPLLSolver(clauses, enc.vars.num_vars)
            var_of = {c: enc.vars.var(c) for c in board.cells()}
            for a in assignments:
                self.assertEqual(cnf_holds(solver, var_of, a), evaluate(clue, board, a),
                                 f"{clue} under {a}")

    def test_exhaustive_3x3(self):
        board = Board.from_dict(load_fixture("puzzle_3x3_basic.json"))
        cells = board.cells()
        assignments = [dict(zip(cells, bits)) for bits in itertools.product((False, True), repeat=9)]
        self.check_board(board, all_clues_3x3(board), assignments)

    def test_random_4x4(self):
        rng = random.Random(4)
        board = Board(4, tuple(Character(f"P{i}", "", f"{chr(65 + i % 4)}{i // 4 + 1}") for i in range(16)))
        cells = board.cells()
        assignments = [{c: rng.random() < 0.5 for c in cells} for _ in range(150)]
        regions = [{"kind": "neighbors", "of": "B2"}, {"kind": "row", "row": 4}, {"kind": "edges"},
                   {"kind": "between", "a": "A1", "b": "A4"}, {"kind": "col", "col": "D"}]
        clues = []
        for i, region in enumerate(regions):
            clues.append(Clue(f"p{i}", "A1", ClueType.PARITY, {"region": region, "parity": "ODD"}))
            clues.append(Clue(f"e{i}", "A1", ClueType.EXACTLY, {"region": region, "k": 2}))
            for j, other in enumerate(regions):
                if i != j:
                    clues.append(Clue(f"c{i}{j}", "A1", ClueType.COMPARE,
                                      {"region_a": region, "region_b": other, "op": "MORE"}))
        self.check_board(board, clues, assignments)

    def test_evaluator_accepts_status_and_bool(self):
        puzzle = load_fixture("puzzle_3x3_basic.json")
        board = Board.from_dict(puzzle)
        clues = [Clue.from_dict(d) for d in puzzle["clues"]]
        solution = {c: Status(s) for c, s in puzzle["solution"].items()}
        self.assertEqual(violated(clues, board, solution), [])
        flipped = dict(solution, A1=Status.CRIMINAL)
        self.assertIn("clue_B2", violated(clues, board, flipped))
        with self.assertRaises(ValueError):
            evaluate(clues[0], board, {"A1": True})


if __name__ == "__main__":
    unittest.main()
