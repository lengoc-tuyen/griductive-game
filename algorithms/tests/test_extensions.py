"""[A] Tests for the extensions: advanced regions, PARITY, COMPARE, counting innocents."""

import unittest

from algorithms.logic import cardinality, regions
from algorithms.logic.clues import ClueValidationError, referenced_cells, validate
from algorithms.logic.encoder import CNFEncoder
from algorithms.logic.models import Board, Clue, ClueType
from algorithms.tests.helpers import brute_force_models, load_fixture


class TestAdvancedRegions(unittest.TestCase):
    def setUp(self):
        self.board = Board.from_dict(load_fixture("puzzle_3x3_basic.json"))

    def r(self, region):
        return regions.resolve(region, self.board)

    def test_corners_edges(self):
        self.assertEqual(self.r({"kind": "corners"}), ["A1", "C1", "A3", "C3"])
        self.assertEqual(self.r({"kind": "edges"}), ["A1", "B1", "C1", "A2", "C2", "A3", "B3", "C3"])

    def test_between(self):
        self.assertEqual(self.r({"kind": "between", "a": "Alice", "b": "Gina"}), ["B1"])  # A1 .. C1
        self.assertEqual(self.r({"kind": "between", "a": "C3", "b": "C1"}), ["C2"])
        self.assertEqual(self.r({"kind": "between", "a": "A1", "b": "A2"}), [])
        with self.assertRaises(regions.RegionError):
            self.r({"kind": "between", "a": "A1", "b": "B2"})

    def test_common_neighbors(self):
        self.assertEqual(self.r({"kind": "common_neighbors", "a": "A1", "b": "C1"}), ["B1", "B2"])
        with self.assertRaises(regions.RegionError):
            self.r({"kind": "common_neighbors", "a": "A1", "b": "Alice"})


class TestExtensionClues(unittest.TestCase):
    def setUp(self):
        self.board = Board.from_dict(load_fixture("puzzle_3x3_basic.json"))

    def test_validation(self):
        bad = [
            Clue("x", "A1", ClueType.PARITY, {"region": {"kind": "row", "row": 1}, "parity": "PRIME"}),
            Clue("x", "A1", ClueType.PARITY, {"region": {"kind": "between", "a": "A1", "b": "A2"},
                                              "parity": "ODD"}),
            Clue("x", "A1", ClueType.COMPARE, {"region_a": {"kind": "row", "row": 1},
                                               "region_b": {"kind": "row", "row": 1}, "op": "MORE"}),
            Clue("x", "A1", ClueType.COMPARE, {"region_a": {"kind": "row", "row": 1},
                                               "region_b": {"kind": "row", "row": 2}, "op": ">"}),
            Clue("x", "A1", ClueType.EXACTLY, {"region": {"kind": "row", "row": 1}, "k": 1, "counts": "X"}),
        ]
        for clue in bad:
            with self.assertRaises(ClueValidationError, msg=clue):
                validate(clue, self.board)

    def test_referenced_cells_of_compare(self):
        clue = Clue("c", "A1", ClueType.COMPARE, {"region_a": {"kind": "row", "row": 1},
                                                  "region_b": {"kind": "col", "col": "A"}, "op": "EQUAL"})
        self.assertEqual(referenced_cells(clue, self.board), ["A1", "B1", "C1", "A2", "A3"])

    def test_aux_variables_are_separate(self):
        enc = CNFEncoder(self.board)
        clue = Clue("p", "A1", ClueType.PARITY, {"region": {"kind": "neighbors", "of": "B2"}, "parity": "ODD"})
        clauses = enc.encode_clue(clue)
        self.assertEqual(enc.vars.num_aux, 7)  # 8 literals -> 7 XOR gates
        aux = {abs(l) for cl in clauses for l in cl if not enc.vars.is_primary(l)}
        self.assertTrue(aux and min(aux) > enc.vars.num_primary)

    def test_counts_innocent(self):
        enc = CNFEncoder(self.board)
        clue = Clue("i", "A1", ClueType.EXACTLY, {"region": {"kind": "row", "row": 1}, "k": 3,
                                                  "counts": "INNOCENT"})
        self.assertEqual(sorted(enc.encode_clue(clue), reverse=True), [[-1], [-2], [-3]])


class TestTseitinEncodings(unittest.TestCase):
    """Brute force over primary AND auxiliary variables (projected on the primaries)."""

    def projected(self, clauses, n, num_vars):
        return {tuple(m[i] for i in range(1, n + 1)) for m in brute_force_models(clauses, num_vars)}

    def test_parity(self):
        for n in range(0, 5):
            for odd in (False, True):
                counter = iter(range(n + 1, 100))
                clauses = cardinality.parity(list(range(1, n + 1)), odd, lambda: next(counter))
                num_vars = next(counter) - 1
                expected = {bits for bits in _bits(n) if sum(bits) % 2 == odd}
                self.assertEqual(self.projected(clauses, n, num_vars), expected, (n, odd))

    def test_compare(self):
        for na in range(0, 3):
            for nb in range(0, 3):
                for op, pred in (("MORE", int.__gt__), ("FEWER", int.__lt__), ("EQUAL", int.__eq__)):
                    n = na + nb
                    counter = iter(range(n + 1, 200))
                    a, b = list(range(1, na + 1)), list(range(na + 1, n + 1))
                    clauses = cardinality.compare(a, b, op, lambda: next(counter))
                    num_vars = next(counter) - 1
                    expected = {bits for bits in _bits(n) if pred(sum(bits[:na]), sum(bits[na:]))}
                    self.assertEqual(self.projected(clauses, n, num_vars), expected, (na, nb, op))


def _bits(n):
    import itertools
    return set(itertools.product((False, True), repeat=n))


if __name__ == "__main__":
    unittest.main()
