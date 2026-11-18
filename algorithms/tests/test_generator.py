"""[E] Unit tests for puzzle generator, loader, cross-checker, and minimization."""

from __future__ import annotations

import copy
import json
import random
import tempfile
import unittest
from pathlib import Path

from algorithms.agent.deduction_agent import AgentOutcome, DeductionAgent
from algorithms.agent.uniqueness import check_uniqueness
from algorithms.logic.models import Board, Clue, ClueType, Status
from algorithms.tests.helpers import FakeEngine, load_fixture
from data.puzzle_loader import Puzzle, PuzzleValidationError, load_puzzle, save_puzzle
from data.scripts.cross_checker import (
    PYSAT_AVAILABLE,
    Z3_AVAILABLE,
    brute_force_verify,
    cross_check_all,
    pysat_verify,
    z3_verify,
)
from data.scripts.generate_puzzles import generate_single_puzzle, minimize_clues
from data.scripts.names_pool import DEFAULT_NAMES, generate_characters

FIXTURE_3X3 = "puzzle_3x3_basic.json"


class TestNamesPool(unittest.TestCase):
    def test_generate_characters_3x3(self):
        chars = generate_characters(3, seed=1)
        self.assertEqual(len(chars), 9)
        names = [c.name for c in chars]
        self.assertEqual(names, sorted(names))
        self.assertEqual(names, DEFAULT_NAMES[:9])
        cells = [c.cell for c in chars]
        self.assertEqual(cells, ['A1', 'B1', 'C1', 'A2', 'B2', 'C2', 'A3', 'B3', 'C3'])

    def test_generate_characters_4x4(self):
        chars = generate_characters(4, seed=2)
        self.assertEqual(len(chars), 16)
        names = [c.name for c in chars]
        self.assertEqual(names, sorted(names))
        self.assertEqual(len(set(c.cell for c in chars)), 16)


class TestPuzzleLoader(unittest.TestCase):
    def setUp(self):
        self.fixture_data = load_fixture(FIXTURE_3X3)

    def test_load_and_to_dict(self):
        puzzle = Puzzle.from_dict(self.fixture_data)
        self.assertEqual(puzzle.size, 3)
        self.assertEqual(len(puzzle.characters), 9)
        self.assertEqual(len(puzzle.clues), 9)
        self.assertEqual(puzzle.solution["A1"], Status.INNOCENT)
        d = puzzle.to_dict()
        self.assertEqual(d["id"], self.fixture_data["id"])
        self.assertEqual(d["size"], 3)

    def test_save_and_reload(self):
        puzzle = Puzzle.from_dict(self.fixture_data)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_puzzle.json"
            save_puzzle(puzzle, path)
            reloaded = load_puzzle(path)
            self.assertEqual(reloaded.id, puzzle.id)
            self.assertEqual(reloaded.size, puzzle.size)
            self.assertEqual(len(reloaded.clues), len(puzzle.clues))

    def test_validation_incomplete_solution(self):
        bad_data = copy.deepcopy(self.fixture_data)
        del bad_data["solution"]["A1"]
        with self.assertRaises(PuzzleValidationError):
            Puzzle.from_dict(bad_data)

    def test_validation_bad_initial(self):
        bad_data = copy.deepcopy(self.fixture_data)
        bad_data["initially_revealed"] = ["Z9"]
        with self.assertRaises(PuzzleValidationError):
            Puzzle.from_dict(bad_data)


class TestCrossChecker(unittest.TestCase):
    def setUp(self):
        self.puzzle = Puzzle.from_dict(load_fixture(FIXTURE_3X3))

    def test_brute_force_on_fixture(self):
        res = brute_force_verify(self.puzzle)
        self.assertTrue(res.available)
        self.assertTrue(res.is_unique)
        self.assertTrue(res.matches_solution)
        self.assertEqual(res.num_solutions, 1)

    def test_pysat_on_fixture(self):
        if not PYSAT_AVAILABLE:
            self.skipTest("pysat is not installed")
        res = pysat_verify(self.puzzle)
        self.assertTrue(res.available)
        self.assertTrue(res.is_unique)
        self.assertTrue(res.matches_solution)

    def test_z3_on_fixture(self):
        if not Z3_AVAILABLE:
            self.skipTest("z3-solver is not installed")
        res = z3_verify(self.puzzle)
        self.assertTrue(res.available)
        self.assertTrue(res.is_unique)
        self.assertTrue(res.matches_solution)

    def test_injected_inconsistency(self):
        """Cross-checker should detect when a puzzle is broken or has no solutions."""
        broken_data = copy.deepcopy(self.puzzle.to_dict())
        # Invert status of a fact clue to create conflict
        for c in broken_data["clues"]:
            if c["type"] == "FACT":
                c["params"]["status"] = "CRIMINAL" if c["params"]["status"] == "INNOCENT" else "INNOCENT"
                break
        broken_puzzle = Puzzle.from_dict(broken_data)
        res_bf = brute_force_verify(broken_puzzle)
        self.assertFalse(res_bf.is_unique)


class TestGenerator(unittest.TestCase):
    def test_generate_single_puzzle_3x3(self):
        rng = random.Random(42)
        puzzle, run = generate_single_puzzle(
            size=3,
            difficulty="EASY",
            puzzle_id="test_gen_3x3",
            min_ratio=0.30,
            max_ratio=0.50,
            minimize=False,
            rng=rng,
        )
        self.assertEqual(puzzle.size, 3)
        self.assertEqual(run.outcome, AgentOutcome.SOLVED)
        self.assertGreaterEqual(len(run.steps), 7)

        # Verify uniqueness
        known = {c: puzzle.solution[c] for c in puzzle.initially_revealed}
        u = check_uniqueness(puzzle.board, puzzle.clues, known)
        self.assertTrue(u.is_unique)

        # Cross check
        cc = cross_check_all(puzzle)
        for name, r in cc.items():
            if r.available:
                self.assertTrue(r.is_unique, f"{name} failed uniqueness")
                self.assertTrue(r.matches_solution, f"{name} solution mismatch")

    def test_minimization(self):
        rng = random.Random(123)
        puzzle, _ = generate_single_puzzle(
            size=3,
            difficulty="HARD",
            puzzle_id="test_min_3x3",
            min_ratio=0.30,
            max_ratio=0.50,
            minimize=False,
            rng=rng,
        )
        minimized = minimize_clues(puzzle)
        self.assertLessEqual(len(minimized.clues), len(puzzle.clues))

        # Must still be unique and solvable
        engine = FakeEngine(minimized.to_dict())
        run = DeductionAgent().run(engine)
        self.assertEqual(run.outcome, AgentOutcome.SOLVED)


if __name__ == "__main__":
    unittest.main()
