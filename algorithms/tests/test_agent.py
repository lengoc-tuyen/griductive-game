"""[C] Tests for entailment classification, verdict checking, hint and the deduction loop."""

import json
import random
import unittest

from algorithms.agent.deduction_agent import AgentOutcome, DeductionAgent
from algorithms.agent.entailment import Classification, check_verdict, classify, classify_all
from algorithms.agent.hint import hint
from algorithms.agent.knowledge_base import build_kb
from algorithms.agent.public_state import PublicState, VerdictResult
from algorithms.agent.uniqueness import Uniqueness, check_uniqueness, enumerate_solutions
from algorithms.logic.models import Board, Clue, ClueType, Status
from algorithms.sat.dpll import solve
from algorithms.tests.helpers import FakeEngine, load_fixture

PUZZLE = "puzzle_3x3_basic.json"
PUZZLE_4X4 = "puzzle_4x4_extensions.json"


def naive_classify(state: PublicState, cell: str) -> Classification:
    """Textbook two-query classification (section 3.4), no witness optimisation."""
    kb = build_kb(state)
    if not solve(kb.cnf.clauses, kb.cnf.num_vars).is_sat:
        return Classification.INCONSISTENT
    v = kb.var_map.var(cell)
    if not solve(kb.cnf.clauses, kb.cnf.num_vars, [-v]).is_sat:
        return Classification.CRIMINAL
    if not solve(kb.cnf.clauses, kb.cnf.num_vars, [v]).is_sat:
        return Classification.INNOCENT
    return Classification.UNKNOWN


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
        self.assertEqual(h.clue_ids, ("clue_B2",))
        self.assertEqual(h.proved_cells, ())
        self.assertIn("Alice", h.message(self.engine.public_state()))

    def test_hint_support_is_irredundant(self):
        engine = FakeEngine(load_fixture(PUZZLE_4X4))
        DeductionAgent(max_steps=6).run(engine)
        state = engine.public_state()
        h = hint(state)
        self.assertIsNotNone(h)
        support = [c for c in state.revealed_clues if c.id in h.clue_ids]
        proved = {c: state.proved[c] for c in h.proved_cells}
        self.assertEqual(naive_classify(PublicState(state.board, tuple(support), proved), h.cell),
                         Classification.of(h.status))
        for drop in support:  # every listed clue is needed
            fewer = tuple(c for c in support if c is not drop)
            self.assertEqual(naive_classify(PublicState(state.board, fewer, proved), h.cell),
                             Classification.UNKNOWN)

    def test_witness_optimisation_matches_naive(self):
        """classify_all must give exactly the textbook answers, with fewer SAT calls."""
        rng = random.Random(1)
        puzzle = load_fixture(PUZZLE_4X4)
        engine = FakeEngine(puzzle)
        board = engine.board
        all_clues = [Clue.from_dict(d) for d in puzzle["clues"]]
        for _ in range(15):
            clues = tuple(rng.sample(all_clues, rng.randint(1, 8)))
            proved = {c: Status(puzzle["solution"][c]) for c in rng.sample(board.cells(), rng.randint(0, 4))}
            state = PublicState(board, clues, proved)
            kb = build_kb(state)
            fast = classify_all(kb)
            self.assertEqual(fast, {c: naive_classify(state, c) for c in state.unresolved_cells()})
            self.assertLessEqual(kb.sat_calls, 1 + len(state.unresolved_cells()))

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

    def test_auto_solve_4x4_with_extensions(self):
        puzzle = load_fixture(PUZZLE_4X4)
        engine = FakeEngine(puzzle)
        run = DeductionAgent().run(engine)
        self.assertEqual(run.outcome, AgentOutcome.SOLVED)
        self.assertEqual({c: s.value for c, s in engine.public_state().proved.items()}, puzzle["solution"])
        self.assertGreater(run.max_aux_vars, 0)
        summary = run.summary()
        self.assertEqual(summary["steps"], 15)
        self.assertEqual(summary["sat_calls"], sum(s.sat_calls for s in run.steps))

    def test_trace(self):
        run = DeductionAgent().run(FakeEngine(load_fixture(PUZZLE)))
        first = run.trace.steps[0]
        self.assertEqual(first.active_clue_ids, ["clue_B2"])
        self.assertEqual(first.revealed_clue_id, "clue_A1")
        self.assertEqual(first.queries[0].description, "KB")
        self.assertTrue(any(q.description == "KB AND C[A1]" and not q.sat for q in first.queries))
        data = json.loads(run.trace.to_json())
        self.assertEqual(data["outcome"], "SOLVED")
        self.assertEqual(len(data["steps"]), 8)
        self.assertIn("Step 1: A1 = INNOCENT", run.trace.to_text())

    def test_stuck_trace_keeps_final_queries(self):
        puzzle = load_fixture(PUZZLE)
        puzzle["clues"] = [d for d in puzzle["clues"] if d["owner"] != "B2"]
        run = DeductionAgent().run(FakeEngine(puzzle))
        self.assertEqual(run.outcome, AgentOutcome.STUCK)
        self.assertEqual(run.steps, [])
        self.assertEqual(len(run.trace.final_queries), run.sat_calls)

    def test_timeout(self):
        run = DeductionAgent(time_limit=0.0).run(FakeEngine(load_fixture(PUZZLE_4X4)))
        self.assertEqual(run.outcome, AgentOutcome.TIMEOUT)

    def test_step_limit(self):
        run = DeductionAgent(max_steps=2).run(FakeEngine(load_fixture(PUZZLE)))
        self.assertEqual(run.outcome, AgentOutcome.STEP_LIMIT)
        self.assertEqual(len(run.steps), 2)


class TestUniqueness(unittest.TestCase):
    def test_fixtures_unique(self):
        for name in (PUZZLE, PUZZLE_4X4):
            puzzle = load_fixture(name)
            board = Board.from_dict(puzzle)
            clues = [Clue.from_dict(d) for d in puzzle["clues"]]
            known = {c: Status(puzzle["solution"][c]) for c in puzzle["initially_revealed"]}
            result = check_uniqueness(board, clues, known)
            self.assertEqual(result.status, Uniqueness.UNIQUE, name)
            self.assertEqual({c: s.value for c, s in result.solutions[0].items()}, puzzle["solution"])

    def test_multiple_and_none(self):
        board = Board.from_dict(load_fixture(PUZZLE))
        self.assertEqual(check_uniqueness(board, []).status, Uniqueness.MULTIPLE)
        self.assertEqual(len(enumerate_solutions(board, [], max_solutions=600).solutions), 512)
        clues = [Clue("s", "A1", ClueType.SAME, {"a": "Alice", "b": "Dan"}),
                 Clue("d", "B1", ClueType.DIFFERENT, {"a": "Alice", "b": "Dan"})]
        self.assertEqual(check_uniqueness(board, clues).status, Uniqueness.NO_SOLUTION)

    def test_aux_variables_do_not_create_fake_solutions(self):
        board = Board.from_dict(load_fixture(PUZZLE))
        clue = Clue("p", "A1", ClueType.PARITY, {"region": {"kind": "row", "row": 1}, "parity": "ODD"})
        result = enumerate_solutions(board, [clue], max_solutions=10_000)
        self.assertEqual(len(result.solutions), 4 * 64)  # 4 odd rows x 2^6 free cells


if __name__ == "__main__":
    unittest.main()
