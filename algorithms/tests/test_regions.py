"""[A] Tests for models, regions and clue validation."""

import unittest

from algorithms.logic import regions
from algorithms.logic.clues import ClueValidationError, validate
from algorithms.logic.models import Board, Clue, ClueType, make_cell, parse_cell
from algorithms.tests.helpers import load_fixture


class TestCells(unittest.TestCase):
    def test_parse_and_make(self):
        self.assertEqual(parse_cell("C2"), (2, 1))
        self.assertEqual(make_cell(2, 1), "C2")
        with self.assertRaises(ValueError):
            parse_cell("c2")

    def test_board_row_major(self):
        board = Board.from_dict(load_fixture("puzzle_3x3_basic.json"))
        self.assertEqual(board.cells()[:4], ["A1", "B1", "C1", "A2"])
        self.assertEqual(board.cell_of("Hank"), "C2")


class TestRegions(unittest.TestCase):
    def setUp(self):
        self.board = Board.from_dict(load_fixture("puzzle_3x3_basic.json"))

    def test_row_col(self):
        self.assertEqual(regions.resolve({"kind": "row", "row": 2}, self.board), ["A2", "B2", "C2"])
        self.assertEqual(regions.resolve({"kind": "col", "col": "B"}, self.board), ["B1", "B2", "B3"])

    def test_neighbors(self):
        self.assertEqual(len(regions.resolve({"kind": "neighbors", "of": "B2"}, self.board)), 8)
        self.assertEqual(regions.resolve({"kind": "neighbors", "of": "A1"}, self.board), ["B1", "A2", "B2"])
        self.assertEqual(regions.resolve({"kind": "neighbors", "of": "Hank"}, self.board),
                         ["B1", "C1", "B2", "B3", "C3"])

    def test_cells(self):
        self.assertEqual(regions.resolve({"kind": "cells", "cells": ["C3", "Alice"]}, self.board), ["A1", "C3"])

    def test_invalid(self):
        for bad in ({"kind": "row", "row": 4}, {"kind": "col", "col": "D"}, {"kind": "cells", "cells": ["A1", "A1"]},
                    {"kind": "neighbors", "of": "Zed"}, {"kind": "diag"}):
            with self.assertRaises(regions.RegionError, msg=bad):
                regions.resolve(bad, self.board)


class TestClueValidation(unittest.TestCase):
    def setUp(self):
        self.board = Board.from_dict(load_fixture("puzzle_3x3_basic.json"))

    def test_fixture_clues_valid(self):
        for d in load_fixture("puzzle_3x3_basic.json")["clues"]:
            validate(Clue.from_dict(d), self.board)

    def test_invalid(self):
        bad = [
            Clue("x", "A1", ClueType.FACT, {"person": "Zed", "status": "CRIMINAL"}),
            Clue("x", "A1", ClueType.FACT, {"person": "Alice", "status": "GUILTY"}),
            Clue("x", "A1", ClueType.SAME, {"a": "Alice", "b": "Alice"}),
            Clue("x", "A1", ClueType.EXACTLY, {"region": {"kind": "row", "row": 1}, "k": 4}),
            Clue("x", "A1", ClueType.AT_MOST, {"region": {"kind": "row", "row": 1}, "k": -1}),
            Clue("x", "Z9", ClueType.FACT, {"person": "Alice", "status": "CRIMINAL"}),
        ]
        for clue in bad:
            with self.assertRaises(ClueValidationError, msg=clue):
                validate(clue, self.board)


if __name__ == "__main__":
    unittest.main()
