"""hanoi: 汉诺塔递归结构工具的朴素实现（改造前基线）。"""

from .core import (
    HanoiError,
    InvalidMoveError,
    InvalidPegError,
    StepOutOfRangeError,
    generate_moves,
    hanoi4,
    is_valid_sequence,
    kth_move,
    min_moves_restricted,
    min_moves_to,
    move_count,
    step_moves,
)

__all__ = [
    "move_count",
    "generate_moves",
    "step_moves",
    "min_moves_to",
    "kth_move",
    "is_valid_sequence",
    "hanoi4",
    "min_moves_restricted",
    "HanoiError",
    "InvalidPegError",
    "InvalidMoveError",
    "StepOutOfRangeError",
]
