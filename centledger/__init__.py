"""centledger：按权重把金额分摊到账户并记账的小库。

用法概览：

    from centledger import BatchRequest, Ledger

    ledger = Ledger()
    result = ledger.apply_batch("B-1", [
        BatchRequest("10.00", {"a": 1, "b": 1, "c": 1}),
    ])
    print(result.render())
    print(ledger.reconcile().render())
"""

from .money import CENT, ZERO, MoneyError, format_cents, from_cents, to_cents
from .allocate import Allocation, allocate, as_amount, as_weight
from .ledger import BatchRequest, BatchResult, Ledger, ReconcileReport

__version__ = "0.4.2"

__all__ = [
    "CENT",
    "ZERO",
    "MoneyError",
    "format_cents",
    "from_cents",
    "to_cents",
    "Allocation",
    "allocate",
    "as_amount",
    "as_weight",
    "BatchRequest",
    "BatchResult",
    "Ledger",
    "ReconcileReport",
]
