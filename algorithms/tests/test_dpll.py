"""[B] Unit tests for the DPLL solver."""

import random
import unittest

from algorithms.sat import cnf
from algorithms.sat.dpll import SATStatus, solve
from algorithms.tests.helpers import brute_force_models


def satisfies(model, clauses):
    return all(any(model[abs(l)] == (l > 0) for l in cl) for cl in clauses)


class TestDPLL(unittest.TestCase):
    def test_empty_formula_sat(self):
        r = solve([], num_vars=3)
        self.assertEqual(r.status, SATStatus.SAT)
        self.assertEqual(set(r.model), {1, 2, 3})

    def test_empty_clause_unsat(self):
        self.assertEqual(solve([[1], []]).status, SATStatus.UNSAT)

    def test_simple_unsat(self):
        self.assertEqual(solve([[1], [-1]]).status, SATStatus.UNSAT)

    def test_spec_example(self):
        # KB = (A v B) ^ (-A v B), A=1, B=2  (section 3.4)
        kb = [[1, 2], [-1, 2]]
        self.assertTrue(solve(kb).is_sat)
        self.assertFalse(solve(kb, assumptions=[-2]).is_sat)  # KB |= B
        self.assertTrue(solve(kb, assumptions=[1]).is_sat)
        self.assertTrue(solve(kb, assumptions=[-1]).is_sat)   # A unknown

    def test_unit_propagation_counts(self):
        r = solve([[1], [-1, 2], [-2, 3]])
        self.assertTrue(r.is_sat)
        self.assertEqual(r.stats.decisions, 0)
        self.assertEqual(r.stats.propagations, 3)
        self.assertEqual(r.model, {1: True, 2: True, 3: True})

    def test_contradictory_assumptions(self):
        self.assertFalse(solve([[1, 2]], assumptions=[3, -3]).is_sat)

    def test_pigeonhole_3_into_2(self):
        # p(i,h): pigeon i in hole h -> var 2*i + h + 1
        def p(i, h):
            return 2 * i + h + 1
        clauses = [[p(i, 0), p(i, 1)] for i in range(3)]
        for h in range(2):
            for i in range(3):
                for j in range(i + 1, 3):
                    clauses.append([-p(i, h), -p(j, h)])
        r = solve(clauses)
        self.assertEqual(r.status, SATStatus.UNSAT)
        self.assertGreater(r.stats.backtracks, 0)

    def test_deterministic(self):
        clauses = [[1, 2, 3], [-1, -2], [-2, -3], [2, 4]]
        self.assertEqual(solve(clauses).model, solve(clauses).model)

    def test_random_vs_brute_force(self):
        rng = random.Random(14003)
        for _ in range(300):
            n = rng.randint(1, 7)
            clauses = [[rng.choice((1, -1)) * rng.randint(1, n) for _ in range(rng.randint(1, 3))]
                       for _ in range(rng.randint(1, 20))]
            expected_sat = next(brute_force_models(clauses, n), None) is not None
            r = solve(clauses, num_vars=n)
            self.assertEqual(r.is_sat, expected_sat, clauses)
            if r.is_sat:
                self.assertTrue(satisfies(r.model, clauses), clauses)

    def test_dimacs_roundtrip(self):
        clauses = [[1, -2], [2, 3], [-1]]
        back, n = cnf.from_dimacs(cnf.to_dimacs(clauses))
        self.assertEqual(back, clauses)
        self.assertEqual(n, 3)


if __name__ == "__main__":
    unittest.main()
