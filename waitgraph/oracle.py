"""全量参考检测：每次现读 registry 的权威登记，从零算一遍。

这是检测器行为的对拍基准，报告规则钉死在这里：候选起点按 pid 升序取，
深搜的后继也按 pid 升序走，路上第一条回到当前路径的边就定环，环成员
从回边落点截到栈顶，再旋转到环上最小 pid 打头。同一张图无论经过怎样
的变动序列，报告恒等。
"""


class FullScan:
    """读 registry 权威状态做全量检测，不维护任何增量状态。"""

    def __init__(self, registry):
        self.registry = registry

    def edges(self):
        """权威等待边，按 (pid, resource, holder) 排序。"""
        return sorted(self.registry.waits())

    def deadlocked(self):
        """现在有没有死锁。"""
        return self.cycle_members() != []

    def cycle_members(self):
        """环上成员，没有环时返回空列表。"""
        collect = {}
        for pid, _, holder in self.registry.waits():
            collect.setdefault(pid, set()).add(holder)
        successors = {pid: sorted(holders) for pid, holders in collect.items()}
        nodes = set(successors)
        for holders in successors.values():
            nodes.update(holders)
        for root in sorted(nodes):
            cycle = self._dfs(root, successors)
            if cycle is not None:
                return cycle
        return []

    def _dfs(self, root, successors):
        path = [root]
        on_path = {root}
        frames = [[root, iter(successors.get(root, ()))]]
        while frames:
            frame = frames[-1]
            nxt = next(frame[1], None)
            if nxt is None:
                frames.pop()
                path.pop()
                on_path.discard(frame[0])
                continue
            if nxt in on_path:
                cycle = path[path.index(nxt):]
                start = cycle.index(min(cycle))
                return cycle[start:] + cycle[:start]
            path.append(nxt)
            on_path.add(nxt)
            frames.append([nxt, iter(successors.get(nxt, ()))])
        return None
