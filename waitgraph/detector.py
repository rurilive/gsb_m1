"""等待图上的死锁检测。

registry 在每次等待关系变动时把事件喂给检测器，检测器维护一份等待图，
回答有没有环、环上是谁。waitgraph.oracle 里的全量实现是这份行为的契约
基准，两边对拍。
"""

from .graph import WaitGraph


class DeadlockDetector:
    """检测器：收变动事件，答死锁判定与环成员。"""

    def __init__(self):
        self.graph = WaitGraph()
        self._deadlocked = False
        self._members = []

    # ---- 事件入口，由 registry 调用 ----

    def note_wait(self, waiter, holder, resource):
        """新等待：waiter 开始等 holder 手里的 resource。"""
        self.graph.add_edge(waiter, holder, resource)
        self._rescan()

    def note_wake(self, waiter, resource, donor):
        """等待结束：donor 把手里的 resource 放给了 waiter。"""
        self.graph.remove_edge(waiter, donor, resource)

    def note_drop(self, pid):
        """进程失联：清掉它留下的等待关系。"""
        self.graph.remove_from(pid)

    def rebuild(self, edges):
        """整体重建（启动加载快照）：edges 是 (waiter, resource, holder)。"""
        self.graph.clear()
        self._deadlocked = False
        self._members = []
        for waiter, resource, holder in edges:
            self.graph.add_edge(waiter, holder, resource)
        self._rescan()

    # ---- 查询 ----

    def deadlocked(self):
        """现在有没有死锁。"""
        return self._deadlocked

    def cycle_members(self):
        """环上成员列表，没有环时为空。"""
        return list(self._members)

    def stats(self):
        """检测过程的访问计数：遍历和整图枚举碰到的节点数。"""
        return {"visits": self.graph.visits, "nodes": self.graph.node_count()}

    def reset_stats(self):
        """访问计数归零。"""
        self.graph.visits = 0

    # ---- 内部实现 ----

    def _rescan(self):
        """从头把整张图扫一遍，找第一个撞上来的环。"""
        self._deadlocked = False
        self._members = []
        for root in self.graph.nodes():
            cycle = self._dfs_cycle(root)
            if cycle is not None:
                self._deadlocked = True
                self._members = cycle
                return

    def _dfs_cycle(self, root):
        """从 root 深搜，撞回当前路径就收工，把走过的整条路径报成环。"""
        path = [root]
        on_path = {root}
        frames = [[root, 0, self.graph.holders(root)]]
        while frames:
            frame = frames[-1]
            successors = frame[2]
            if frame[1] >= len(successors):
                frames.pop()
                path.pop()
                on_path.discard(frame[0])
                continue
            nxt = successors[frame[1]]
            frame[1] += 1
            if nxt in on_path:
                return list(path)
            path.append(nxt)
            on_path.add(nxt)
            frames.append([nxt, 0, self.graph.holders(nxt)])
        return None
