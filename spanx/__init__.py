"""spanx：序列左右边界的朴素工具箱（纯标准库，无外部依赖）。"""

from .spans import (
    EmptyInputError,
    InvalidInputError,
    SpanError,
    count_naive_visits,
    daily_temperatures,
    first_greater_left,
    first_greater_right,
    first_smaller_left,
    first_smaller_right,
    greater_bounds,
    histogram_bounds,
    largest_rectangle,
    min_range_lengths,
    smaller_bounds,
)

__all__ = [
    "SpanError",
    "EmptyInputError",
    "InvalidInputError",
    "first_greater_left",
    "first_greater_right",
    "first_smaller_left",
    "first_smaller_right",
    "greater_bounds",
    "smaller_bounds",
    "min_range_lengths",
    "daily_temperatures",
    "histogram_bounds",
    "largest_rectangle",
    "count_naive_visits",
]
