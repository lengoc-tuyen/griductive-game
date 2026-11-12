"""[D1] Automated unit and API integration tests for GameEngine, clue_renderer, and Web API."""

from __future__ import annotations

import unittest

from algorithms.agent.deduction_agent import AgentOutcome, DeductionAgent
from algorithms.logic.models import Board, Clue, ClueType, Status
from algorithms.tests.helpers import FIXTURES, load_fixture
from frontend.engine.game_engine import GameEngine
from frontend.engine.verdict import VerdictResult
from frontend.gui.app import GriductiveWebService, _DEV_CONSOLE_HTML
from frontend.gui.clue_renderer import get_highlight_cells, render_clue_text

PUZZLE_NAME = "puzzle_3x3_basic.json"


class TestClueRenderer(unittest.TestCase):
    def setUp(self) -> None:
        self.puzzle = load_fixture(PUZZLE_NAME)
        self.board = Board.from_dict(self.puzzle)

    def test_render_all_core_clue_types(self) -> None:
        f_clue = Clue("c1", "A1", ClueType.FACT, {"person": "Gina", "status": "INNOCENT"})
        self.assertIn("Gina is innocent", render_clue_text(f_clue, self.board))

        s_clue = Clue("c2", "A1", ClueType.SAME, {"a": "Finn", "b": "Ivy"})
        self.assertIn("same status", render_clue_text(s_clue, self.board))

        d_clue = Clue("c3", "A1", ClueType.DIFFERENT, {"a": "Alice", "b": "Dan"})
        self.assertIn("different statuses", render_clue_text(d_clue, self.board))

        z_clue = Clue(
            "c4",
            "B2",
            ClueType.AT_MOST,
            {"region": {"kind": "cells", "cells": ["A1", "A2"]}, "k": 0},
        )
        self.assertIn("no criminals", render_clue_text(z_clue, self.board).lower())
        self.assertEqual(get_highlight_cells(z_clue, self.board), ["A1", "A2"])

        e_clue = Clue("c5", "A1", ClueType.EXACTLY, {"region": {"kind": "row", "row": 1}, "k": 1})
        self.assertIn("Exactly 1 criminal in row 1", render_clue_text(e_clue, self.board))
        self.assertEqual(get_highlight_cells(e_clue, self.board), ["A1", "B1", "C1"])


class TestGameEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = GameEngine.from_file(FIXTURES / PUZZLE_NAME)

    def test_initial_public_state_hides_unrevealed(self) -> None:
        state = self.engine.serialize_state()
        self.assertEqual(state["puzzle_id"], "test_3x3_basic")
        self.assertEqual(state["size"], 3)
        self.assertFalse(state["is_solved"])
        self.assertEqual(state["proved_count"], 1)
        self.assertEqual(state["total_cells"], 9)

        by_cell = {c["cell"]: c for c in state["cards"]}
        self.assertTrue(by_cell["B2"]["is_revealed"])
        self.assertEqual(by_cell["B2"]["status"], "INNOCENT")
        self.assertIsNotNone(by_cell["B2"]["clue_text"])
        self.assertEqual(by_cell["B2"]["highlight_cells"], ["A1", "A2"])

        self.assertFalse(by_cell["A1"]["is_revealed"])
        self.assertIsNone(by_cell["A1"]["status"])
        self.assertIsNone(by_cell["A1"]["clue_text"])
        self.assertEqual(by_cell["A1"]["highlight_cells"], [])

    def test_verdict_distinguishes_accepted_not_provable_contradicted(self) -> None:
        # B1 is not yet forced -> NOT_PROVABLE
        r_unprovable = self.engine.submit_verdict("B1", Status.CRIMINAL)
        self.assertEqual(r_unprovable.result, VerdictResult.NOT_PROVABLE)
        self.assertIsNone(r_unprovable.revealed_clue)

        # A1 is forced INNOCENT, so calling CRIMINAL -> CONTRADICTED
        r_contradicted = self.engine.submit_verdict("A1", Status.CRIMINAL)
        self.assertEqual(r_contradicted.result, VerdictResult.CONTRADICTED)
        self.assertIsNone(r_contradicted.revealed_clue)

        # A1 calling INNOCENT -> ACCEPTED and reveals clue_A1
        r_accepted = self.engine.submit_verdict("A1", Status.INNOCENT)
        self.assertEqual(r_accepted.result, VerdictResult.ACCEPTED)
        self.assertIsNotNone(r_accepted.revealed_clue)
        self.assertEqual(r_accepted.revealed_clue["id"], "clue_A1")

    def test_engine_protocol_compatibility(self) -> None:
        # Verify GameEngine satisfies EngineProtocol for [C] DeductionAgent
        run = DeductionAgent().run(self.engine)
        self.assertEqual(run.outcome, AgentOutcome.SOLVED)
        self.assertTrue(self.engine.public_state().is_solved())


class TestWebServiceAPI(unittest.TestCase):
    def setUp(self) -> None:
        self.service = GriductiveWebService(initial_puzzle_path=FIXTURES / PUZZLE_NAME)

    def test_core_d1_api_workflow(self) -> None:
        # 1. GET /api/puzzles
        puzzles = self.service.list_puzzles()
        self.assertGreaterEqual(len(puzzles), 1)

        # 2. POST /api/restart
        restart_res = self.service.restart()
        self.assertTrue(restart_res["ok"])
        self.assertEqual(restart_res["state"]["proved_count"], 1)

        # 3. POST /api/verdict (NOT_PROVABLE vs CONTRADICTED vs ACCEPTED)
        bad_verdict = self.service.submit_verdict({"cell": "B1", "status": "CRIMINAL"})
        self.assertEqual(bad_verdict["result"], "NOT_PROVABLE")

        contra_verdict = self.service.submit_verdict({"cell": "A1", "status": "CRIMINAL"})
        self.assertEqual(contra_verdict["result"], "CONTRADICTED")

        good_verdict = self.service.submit_verdict({"cell": "A1", "status": "INNOCENT"})
        self.assertEqual(good_verdict["result"], "ACCEPTED")
        self.assertEqual(good_verdict["state"]["proved_count"], 2)

    def test_load_custom_puzzle_json(self) -> None:
        raw = load_fixture(PUZZLE_NAME)
        res = self.service.load_puzzle({"puzzle": raw})
        self.assertTrue(res["ok"])
        self.assertEqual(res["state"]["puzzle_id"], "test_3x3_basic")

    def test_dev_console_html_embedded(self) -> None:
        self.assertIn("D1 Engine & API Test Console", _DEV_CONSOLE_HTML)
        self.assertIn("/api/verdict", _DEV_CONSOLE_HTML)


if __name__ == "__main__":
    unittest.main()
