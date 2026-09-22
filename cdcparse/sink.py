"""下游内存实现。

下游只认变更字典，apply 一次收一批；批内顺序就是下游看到的顺序。
"""


class MemorySink:
    """把收到的变更原样存下来的内存下游。"""

    def __init__(self):
        self._changes = []
        self.batches = 0
        self.received = 0
        self.last_pos = 0

    def apply(self, changes):
        """收下一批变更，返回本批条数。

        逐条浅拷贝，避免调用方事后改动字典影响下游记录。
        """
        batch = []
        for change in changes:
            item = dict(change)
            batch.append(item)
            pos = item.get("pos", 0)
            if isinstance(pos, int) and pos > self.last_pos:
                self.last_pos = pos
        self._changes.extend(batch)
        self.batches += 1
        self.received += len(batch)
        return len(batch)

    def changes(self):
        """按到达顺序返回变更快照，逐条拷贝。"""
        return [dict(item) for item in self._changes]

    def pos_list(self):
        """变更位点列表，方便断言顺序与去重。"""
        return [item.get("pos", 0) for item in self._changes]

    def stats(self):
        return {
            "batches": self.batches,
            "changes": self.received,
            "last_pos": self.last_pos,
        }

    def __repr__(self):
        return "MemorySink(batches=%d, changes=%d)" % (
            self.batches, self.received)
