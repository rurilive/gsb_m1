"""最朴素的事务引擎：一把全局锁把事务从头到尾串行化。

LockedTxn 在 begin 时抢下一把全局锁并一直持有到 commit 或 rollback，期间
读写彼此互斥，前后事务之间没有任何重叠。数据直接落在一块共享存储上，回滚
靠把整块存储恢复成 begin 时保存的副本。这里没有快照、没有版本链、没有并发
读写，也没有任何冲突检测。
"""

import threading


class TxnError(Exception):
    """txbox 的异常基类，所有引擎异常都从它派生。"""


class TxnStateError(TxnError):
    """事务状态非法，例如重复提交、已结束事务再操作。"""


class LockedTxn:
    """全局锁串行化的事务引擎。

    begin() 抢锁并开启事务；get/set/delete 读写共享存储；commit() 生效并
    放锁；rollback() 恢复 begin 时的整块副本并放锁。同一时刻只允许一个事务
    在跑，重复 begin 直接失败。
    """

    def __init__(self, initial=None):
        self._data = dict(initial or {})
        self._backup = None
        self._active = False
        self._lock = threading.Lock()

    @property
    def committed(self):
        """当前已提交数据的浅拷贝，不依赖是否有事务在跑。"""
        return dict(self._data)

    def begin(self):
        if self._active:
            raise TxnStateError("已有事务在进行，全局锁串行化，同一时刻只允许一个事务")
        if not self._lock.acquire(blocking=False):
            raise TxnStateError("全局锁被占用，无法开启事务")
        self._backup = dict(self._data)
        self._active = True
        return self

    def _require(self):
        if not self._active:
            raise TxnStateError("没有进行中的事务，请先 begin")

    def get(self, key):
        self._require()
        return self._data.get(key)

    def set(self, key, value):
        self._require()
        self._data[key] = value

    def delete(self, key):
        self._require()
        self._data.pop(key, None)

    def commit(self):
        self._require()
        self._active = False
        self._backup = None
        self._lock.release()

    def rollback(self):
        self._require()
        self._data = self._backup
        self._backup = None
        self._active = False
        self._lock.release()

    @property
    def active(self):
        return self._active
