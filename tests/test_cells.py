"""格网切分的既有行为锁定。"""

import unittest

from geogrid.cells import DEFAULT_CELL_DEG, cell_col, cell_of, cell_row, check_cell_deg, per_degree


class CheckCellDegTest(unittest.TestCase):
    def test_positive_fractions_of_a_degree_pass(self):
        self.assertEqual(check_cell_deg(0.05), 0.05)
        self.assertEqual(check_cell_deg(1.0), 1.0)
        self.assertEqual(check_cell_deg(0.5), 0.5)

    def test_bad_edges_rejected(self):
        for bad in (0.0, -0.05, 7.0, 100.0, "0.05", True, float("inf")):
            with self.assertRaises(ValueError):
                check_cell_deg(bad)

    def test_per_degree(self):
        self.assertEqual(per_degree(DEFAULT_CELL_DEG), 20)
        self.assertEqual(per_degree(1.0), 1)


class CellTest(unittest.TestCase):
    def test_origin_and_corners(self):
        self.assertEqual(cell_of(0.0, 0.0, 0.05), (1800, 3600))
        self.assertEqual(cell_of(-90.0, -180.0, 0.05), (0, 0))
        self.assertEqual(cell_of(0.0, 179.999, 0.05), (1800, 7199))

    def test_lon_180_lands_in_the_first_column(self):
        self.assertEqual(cell_col(180.0, 0.05), 0)
        self.assertEqual(cell_col(-180.0, 0.05), 0)
        self.assertEqual(cell_col(190.0, 0.05), cell_col(-170.0, 0.05))

    def test_neighbours_share_or_touch_edges(self):
        base_row = cell_row(31.2, 0.05)
        self.assertEqual(cell_row(31.2, 0.05), base_row)
        self.assertEqual(cell_row(31.2499, 0.05), base_row)
        self.assertEqual(cell_row(31.25, 0.05), base_row + 1)


if __name__ == "__main__":
    unittest.main()
