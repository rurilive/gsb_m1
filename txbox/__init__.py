"""txbox：纯标准库的事务小引擎。

当前只导出最朴素的全局锁事务 LockedTxn 及其异常基类。
"""

from .engine import LockedTxn, TxnError

__all__ = ["LockedTxn", "TxnError"]
