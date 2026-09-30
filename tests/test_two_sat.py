"""朴素二可满足性实现的基线行为测试。

锁住改造前的现状: 枚举求解的赋值口径、可满足判定、解计数、赋值校验,
以及异常基类与非法输入的拒绝方式。本文件在改造后一字不许改, 且必须一直
全绿。
"""

import unittest

from twosat import (
    BadAssignmentError,
    BadClauseError,
    BadLiteralError,
    BadVariableCountError,
    Erro,
    UnsatisfiableError,
    count_solutions,
    is_satisfiable,
    require_solution,
    solve,
    verify,
)


class TestErrors(unittest.TestCase):
    def test_all_errors_share_base(self):
        for exc in (BadVariableCountError, BadClauseError, BadLiteralError,
                    BadAssignmentError, UnsatisfiableError):
            self.assertTrue(issubclass(exc, Erro))
            self.assertTrue(issubclass(exc, Exception))


class TestSolveBasics(unittest.TestCase):
    def test_zero_variables(self):
        self.assertEqual(solve(0, []), {})
        self.assertTrue(is_satisfiable(0, []))
        self.assertEqual(count_solutions(0, []), 1)

    def test_no_clauses_first_assignment_is_all_false(self):
        self.assertEqual(solve(3, []), {1: False, 2: False, 3: False})
        self.assertEqual(count_solutions(3, []), 8)

    def test_single_clause_picks_first_mask(self):
        self.assertEqual(solve(2, [(1, 2)]), {1: True, 2: False})
        self.assertEqual(count_solutions(2, [(1, 2)]), 3)

    def test_tautology_keeps_all(self):
        self.assertEqual(solve(1, [(1, -1)]), {1: False})
        self.assertEqual(count_solutions(1, [(1, -1)]), 2)

    def test_unsatisfiable_returns_none(self):
        self.assertIsNone(solve(1, [(1, 1), (-1, -1)]))
        self.assertFalse(is_satisfiable(1, [(1, 1), (-1, -1)]))
        self.assertEqual(count_solutions(1, [(1, 1), (-1, -1)]), 0)

    def test_require_solution_raises(self):
        with self.assertRaises(UnsatisfiableError):
            require_solution(1, [(1, 1), (-1, -1)])
        self.assertEqual(require_solution(2, [(1, 2)]), {1: True, 2: False})

    def test_solution_is_deterministic(self):
        clauses = [(1, 2), (-2, 3), (-1, -3)]
        first = solve(3, clauses)
        second = solve(3, clauses)
        self.assertEqual(first, second)
        self.assertEqual(count_solutions(3, clauses), 2)


class TestVerify(unittest.TestCase):
    def test_verify_true_and_false(self):
        clauses = [(1, 2)]
        self.assertTrue(verify(2, clauses, {1: True, 2: False}))
        self.assertFalse(verify(2, clauses, {1: False, 2: False}))

    def test_verify_accepts_zero_one_int(self):
        self.assertTrue(verify(1, [(1, 1)], {1: 1}))

    def test_verify_rejects_bad_assignment(self):
        with self.assertRaises(BadAssignmentError):
            verify(2, [(1, 2)], {1: True})
        with self.assertRaises(BadAssignmentError):
            verify(1, [(1, 1)], {1: 2})
        with self.assertRaises(BadAssignmentError):
            verify(1, [(1, 1)], [True])


class TestValidation(unittest.TestCase):
    def test_bad_variable_count(self):
        with self.assertRaises(BadVariableCountError):
            solve(-1, [])
        with self.assertRaises(BadVariableCountError):
            solve(True, [])
        with self.assertRaises(BadVariableCountError):
            solve("2", [])

    def test_bad_clause_shape(self):
        with self.assertRaises(BadClauseError):
            solve(2, [(1,)])
        with self.assertRaises(BadClauseError):
            solve(2, [7])

    def test_bad_literal(self):
        with self.assertRaises(BadLiteralError):
            solve(2, [(0, 1)])
        with self.assertRaises(BadLiteralError):
            solve(2, [(3, 1)])
        with self.assertRaises(BadLiteralError):
            solve(2, [(True, 1)])
        with self.assertRaises(BadLiteralError):
            solve(2, [("1", 1)])

    def test_validation_is_checked_before_enumeration(self):
        with self.assertRaises(BadClauseError):
            is_satisfiable(2, [(1,)])
        with self.assertRaises(BadClauseError):
            count_solutions(2, [(1,)])


if __name__ == "__main__":
    unittest.main()
