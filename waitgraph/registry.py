"""等待关系的登记簿：谁拿着哪些资源，谁在排队等哪个资源。

registry 是等待关系的事实来源；环检测挂在它身上的检测器里，状态一变
就把事件喂过去。进程正常 release，资源交给队头；异常 drop 表示进程
失联，它排的队作废，它手里的资源直接收回不转交，等着这些资源的进程
一并作废。
"""

from .detector import DeadlockDetector


class RegistryError(RuntimeError):
    """登记操作不合法。"""


class NotHeld(RegistryError):
    """没有拿着这个资源。"""


class AlreadyHeld(RegistryError):
    """已经拿着或者已经在等这个资源。"""


class ResourceRegistry:
    """资源与等待关系的登记簿。

    detector 是挂上的检测器，默认新起一个 DeadlockDetector；也可以传入
    别的实现做对照。
    """

    def __init__(self, detector=None):
        self.detector = detector if detector is not None else DeadlockDetector()
        self._holders = {}
        self._queues = {}
        self._waits = {}

    # ---- 登记 ----

    def acquire(self, pid, resource):
        """申请资源：空着就当场持有，返回 True；被占就进队等待，返回 False。"""
        holder = self._holders.get(resource)
        if holder is None:
            self._holders[resource] = pid
            return True
        if holder == pid:
            raise AlreadyHeld("%r 已经拿着 %r" % (pid, resource))
        if resource in self._waits.get(pid, {}):
            raise AlreadyHeld("%r 已经在等 %r" % (pid, resource))
        self._queues.setdefault(resource, []).append(pid)
        self._waits.setdefault(pid, {})[resource] = holder
        self.detector.note_wait(pid, holder, resource)
        return False

    def release(self, pid, resource):
        """放掉自己拿的资源，队头接手并返回接手者 pid；没人等返回 None。"""
        if self._holders.get(resource) != pid:
            raise NotHeld("%r 没拿着 %r" % (pid, resource))
        queue = self._queues.get(resource)
        if not queue:
            del self._holders[resource]
            return None
        nxt = queue.pop(0)
        if not queue:
            del self._queues[resource]
        self._holders[resource] = nxt
        del self._waits[nxt][resource]
        if not self._waits[nxt]:
            del self._waits[nxt]
        self.detector.note_wake(nxt, resource, pid)
        for other in queue:
            self._waits[other][resource] = nxt
            self.detector.note_wait(other, nxt, resource)
        return nxt

    def drop(self, pid):
        """进程失联：返回被作废的 (pid, resource) 列表。"""
        aborted = []
        for resource in list(self._waits.get(pid, ())):
            self._dequeue(resource, pid)
            aborted.append((pid, resource))
        self._waits.pop(pid, None)
        for resource, holder in list(self._holders.items()):
            if holder != pid:
                continue
            del self._holders[resource]
            for other in self._queues.pop(resource, ()):
                self._waits.get(other, {}).pop(resource, None)
                if not self._waits.get(other):
                    self._waits.pop(other, None)
                aborted.append((other, resource))
        self.detector.note_drop(pid)
        return aborted

    def load_state(self, holds, waits):
        """启动时从状态快照整体恢复。

        holds 是 {资源: pid}，waits 是 [(pid, 资源, holder)]；喂给检测器
        时走整体重建，不做逐条检测。
        """
        self._holders = dict(holds)
        self._queues = {}
        self._waits = {}
        for pid, resource, holder in waits:
            self._waits.setdefault(pid, {})[resource] = holder
            self._queues.setdefault(resource, []).append(pid)
        self.detector.rebuild(sorted(self.waits()))

    def _dequeue(self, resource, pid):
        queue = self._queues.get(resource)
        if queue and pid in queue:
            queue.remove(pid)
            if not queue:
                del self._queues[resource]

    # ---- 查询 ----

    def holder(self, resource):
        """资源现在在谁手里。"""
        return self._holders.get(resource)

    def waiters(self, resource):
        """排队等这个资源的人，按先后顺序。"""
        return list(self._queues.get(resource, ()))

    def pending(self, pid):
        """pid 正在等的东西，{资源: holder}。"""
        return dict(self._waits.get(pid, {}))

    def waits(self):
        """权威等待边，元素是 (pid, resource, holder)。"""
        return [(pid, resource, holder)
                for pid, slots in self._waits.items()
                for resource, holder in slots.items()]

    def holds(self, pid):
        """pid 手里拿着的资源。"""
        return sorted(res for res, holder in self._holders.items() if holder == pid)

    def health(self):
        """运维探针：现在有没有死锁，环上是谁。"""
        return {"deadlocked": self.detector.deadlocked(),
                "cycle": self.detector.cycle_members()}
