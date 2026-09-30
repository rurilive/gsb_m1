"""TwoSat 现有行为的锁定测试（基线，一字不改）。"""

import unittest

from satx.twosat import (
    InvalidAssignmentError,
    InvalidLiteralError,
    SatError,
    TwoSat,
)


class TestTwoSat(unittest.TestCase):
    def test_empty_clause_set_is_satisfiable(self):
        sat = TwoSat(3)
        self.assertTrue(sat.is_satisfiable())
        self.assertEqual(sat.solve(), {1: False, 2: False, 3: False})
        self.assertEqual(sat.clause_count(), 0)

    def test_single_variable_positive_clause(self):
        sat = TwoSat(1).add_clause(1, 1)
        self.assertTrue(sat.is_satisfiable())
        self.assertEqual(sat.solve(), {1: True})
        self.assertEqual(sat.value_of(1), True)

    def test_contradiction_is_unsatisfiable(self):
        sat = TwoSat(1).add_clause(1, 1).add_clause(-1, -1)
        self.assertFalse(sat.is_satisfiable())
        self.assertIsNone(sat.solve())
        self.assertIsNone(sat.value_of(1))
        self.assertEqual(sat.count_models(), 0)

    def test_implication_chain(self):
        sat = TwoSat(2).add_clause(-1, 2).add_clause(1, 1)
        self.assertTrue(sat.is_satisfiable())
        self.assertEqual(sat.solve(), {1: True, 2: True})

    def test_two_variable_clause_has_three_models(self):
        sat = TwoSat(2).add_clause(1, 2)
        self.assertEqual(sat.count_models(), 3)
        self.assertTrue(sat.is_satisfiable())

    def test_clauses_returns_copy_in_order(self):
        sat = TwoSat(2).add_clause(1, 2).add_clause(-2, 1)
        got = sat.clauses()
        self.assertEqual(got, [(1, 2), (-2, 1)])
        got.append((1, 1))
        self.assertEqual(sat.clause_count(), 2)

    def test_satisfied_count_on_given_assignment(self):
        sat = TwoSat(2).add_clause(1, 2).add_clause(-1, -2)
        self.assertEqual(sat.satisfied_count({1: True, 2: True}), 1)
        self.assertEqual(sat.satisfied_count({1: True, 2: False}), 2)

    def test_enumeration_size_grows_exponentially(self):
        self.assertEqual(TwoSat(0).enumeration_size(), 1)
        self.assertEqual(TwoSat(4).enumeration_size(), 16)

    def test_var_count_zero_with_tautology_clause(self):
        sat = TwoSat(1).add_clause(1, -1)
        self.assertTrue(sat.is_satisfiable())
        self.assertEqual(sat.count_models(), 2)

    def test_literal_zero_rejected(self):
        with self.assertRaises(InvalidLiteralError):
            TwoSat(2).add_clause(0, 1)

    def test_literal_out_of_range_rejected(self):
        with self.assertRaises(InvalidLiteralError):
            TwoSat(2).add_clause(3, 1)

    def test_non_integer_literal_rejected(self):
        with self.assertRaises(InvalidLiteralError):
            TwoSat(2).add_clause(1.5, 1)

    def test_negative_var_count_rejected(self):
        with self.assertRaises(SatError):
            TwoSat(-1)

    def test_assignment_must_cover_all_variables(self):
        sat = TwoSat(2).add_clause(1, 2)
        with self.assertRaises(InvalidAssignmentError):
            sat.satisfied_count({1: True})

    def test_assignment_value_must_be_bool(self):
        sat = TwoSat(1)
        with self.assertRaises(InvalidAssignmentError):
            sat.satisfied_count({1: 1})

    def test_error_base_class(self):
        self.assertTrue(issubclass(InvalidLiteralError, SatError))
        self.assertTrue(issubclass(InvalidAssignmentError, SatError))
        self.assertTrue(issubclass(SatError, Exception))

    def test_deterministic_repeat(self):
        sat = TwoSat(3).add_clause(1, 2).add_clause(-2, 3)
        self.assertEqual(sat.solve(), sat.solve())
        self.assertEqual(sat.count_models(), sat.count_models())


if __name__ == "__main__":
    unittest.main()
