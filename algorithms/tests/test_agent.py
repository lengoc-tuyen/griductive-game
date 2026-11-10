"""[C] Tests for entailment classification, verdict checking, hint and the deduction loop."""

import unittest

from algorithms.agent.deduction_agent import AgentOutcome, DeductionAgent
from algorithms.agent.entailment import Classification, check_verdict, classify, classify_all
from algorithms.agent.hint import hint
from algorithms.agent.knowledge_base import build_kb
from algorithms.agent.public_state import PublicState, VerdictResult
from algorithms.logic.models import Board, Clue, ClueType, Status
from algorithms.tests.helpers import FakeEngine, load_fixture

PUZZLE = "puzzle_3x3_basic.json"


class TestEntailment(unittest.TestCase):
    def setUp(self):
        self.engine = FakeEngine(load_fixture(PUZZLE))

    def test_initial_classification(self):
        kb = build_kb(self.engine.public_state())
        result = classify_all(kb)
        self.assertEqual(result["A1"], Classification.INNOCENT)
        self.assertEqual(result["A2"], Classification.INNOCENT)
        self.assertEqual(result["B1"], Classification.UNKNOWN)
        self.assertNotIn("B2", result)  # already proved

    def test_check_verdict(self):
        state = self.engine.public_state()
        self.assertEqual(check_verdict(state, "A1", Status.INNOCENT), VerdictResult.ACCEPTED)
        self.assertEqual(check_verdict(state, "A1", Status.CRIMINAL), VerdictResult.CONTRADICTED)
        self.assertEqual(check_verdict(state, "B1", Status.CRIMINAL), VerdictResult.NOT_PROVABLE)

    def test_rejected_verdict_leaves_state_unchanged(self):
        before = self.engine.public_state()
        result, clue = self.engine.submit("B1", Status.CRIMINAL)
        self.assertEqual(result, VerdictResult.NOT_PROVABLE)
        self.assertIsNone(clue)
        self.assertEqual(self.engine.public_state(), before)

    def test_inconsistent(self):
        board = Board.from_dict(load_fixture(PUZZLE))
        clues = (
            Clue("s", "A1", ClueType.SAME, {"a": "Alice", "b": "Dan"}),
            Clue("d", "B1", ClueType.DIFFERENT, {"a": "Alice", "b": "Dan"}),
        )
        kb = build_kb(PublicState(board, clues, {}))
        self.assertEqual(classify(kb, "C3"), Classification.INCONSISTENT)
        with self.assertRaises(ValueError):
            hint(PublicState(board, clues, {}))

    def test_hint(self):
        h = hint(self.engine.public_state())
        self.assertEqual((h.cell, h.status), ("A1", Status.INNOCENT))

    def test_no_clues_nothing_forced(self):
        board = Board.from_dict(load_fixture(PUZZLE))
        self.assertIsNone(hint(PublicState(board)))


class TestDeductionLoop(unittest.TestCase):
    def test_auto_solve(self):
        puzzle = load_fixture(PUZZLE)
        engine = FakeEngine(puzzle)
        run = DeductionAgent().run(engine)
        self.assertEqual(run.outcome, AgentOutcome.SOLVED)
        self.assertEqual(len(run.steps), 8)
        self.assertEqual({c: s.value for c, s in engine.public_state().proved.items()}, puzzle["solution"])
        self.assertEqual([s.cell for s in run.steps][:3], ["A1", "A2", "B1"])
        self.assertGreater(run.sat_calls, 0)
        self.assertEqual(run.max_primary_vars, 9)

    def test_stuck(self):
        puzzle = load_fixture(PUZZLE)
        # replace B1's clue with a tautology -> C2 can no longer be forced from row 2
        for d in puzzle["clues"]:
            if d["owner"] == "B1":
                d["type"], d["params"] = "AT_MOST", {"region": {"kind": "row", "row": 2}, "k": 3}
        run = DeductionAgent().run(FakeEngine(puzzle))
        self.assertEqual(run.outcome, AgentOutcome.STUCK)

    def test_step_limit(self):
        run = DeductionAgent(max_steps=2).run(FakeEngine(load_fixture(PUZZLE)))
        self.assertEqual(run.outcome, AgentOutcome.STEP_LIMIT)
        self.assertEqual(len(run.steps), 2)


if __name__ == "__main__":
    unittest.main()
