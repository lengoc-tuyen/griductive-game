"""[A] Tests for cardinality encodings and the CNF encoder (brute-force checked).

The cross-test against the semantic evaluator (test_encoder_vs_evaluator.py) is
planned once ``evaluator.py`` exists.
"""

import itertools
import unittest

from algorithms.logic import cardinality
from algorithms.logic.encoder import CNFEncoder
from algorithms.logic.models import Board, Clue, ClueType, Status
from algorithms.tests.helpers import brute_force_models, load_fixture


class TestCardinality(unittest.TestCase):
    def test_against_brute_force(self):
        for n in range(0, 6):
            lits = list(range(1, n + 1))
            for k in range(-1, n + 2):
                for name, fn, pred in (
                    ("at_most", cardinality.at_most, lambda s: s <= k),
                    ("at_least", cardinality.at_least, lambda s: s >= k),
                    ("exactly", cardinality.exactly, lambda s: s == k),
                ):
                    clauses = fn(lits, k)
                    for bits in itertools.product((False, True), repeat=n):
                        a = {i + 1: b for i, b in enumerate(bits)}
                        cnf_true = all(any(a[abs(l)] == (l > 0) for l in cl) for cl in clauses)
                        self.assertEqual(cnf_true, pred(sum(bits)), f"{name} n={n} k={k} bits={bits}")


class TestEncoder(unittest.TestCase):
    def setUp(self):
        self.board = Board.from_dict(load_fixture("puzzle_3x3_basic.json"))
        self.enc = CNFEncoder(self.board)

    def test_binary_clues(self):
        a, b = self.enc.vars.var("A1"), self.enc.vars.var("B1")
        self.assertEqual(self.enc.encode_clue(Clue("s", "A1", ClueType.SAME, {"a": "Alice", "b": "Dan"})),
                         [[-a, b], [a, -b]])
        self.assertEqual(self.enc.encode_clue(Clue("d", "A1", ClueType.DIFFERENT, {"a": "Alice", "b": "Dan"})),
                         [[a, b], [-a, -b]])
        self.assertEqual(self.enc.encode_clue(Clue("f", "A1", ClueType.FACT,
                                                   {"person": "Alice", "status": "INNOCENT"})), [[-a]])

    def test_verdict_unit_clause(self):
        v = self.enc.vars.var("C2")
        self.assertEqual(self.enc.encode_verdict("C2", Status.CRIMINAL), [v])
        self.assertEqual(self.enc.encode_verdict("C2", Status.INNOCENT), [-v])

    def test_full_fixture_has_unique_model_equal_to_solution(self):
        puzzle = load_fixture("puzzle_3x3_basic.json")
        clues = [Clue.from_dict(d) for d in puzzle["clues"]]
        # initially revealed statuses are part of the public knowledge
        initial = {c: Status(puzzle["solution"][c]) for c in puzzle["initially_revealed"]}
        encoded = self.enc.encode(clues, initial)
        self.assertEqual(encoded.num_primary, 9)
        self.assertEqual(encoded.num_aux, 0)
        models = list(brute_force_models(encoded.clauses, encoded.num_vars))
        self.assertEqual(len(models), 1)
        expected = {self.enc.vars.var(c): s == "CRIMINAL" for c, s in puzzle["solution"].items()}
        self.assertEqual(models[0], expected)


if __name__ == "__main__":
    unittest.main()
