"""成员的一条状态记录。

现在这条记录是静态的：一个成员名、一个存活标志、一个最后被看见的时间。
它不带版本号，也不带怀疑与死亡的中间态，节点之间交换的也只是这张表的
一份快照，谁的时间更新就以谁为准。
"""


class MemberRecord:
    """一个成员当前被本节点看到的模样。

    name 是成员名，alive 是存活标志，last_seen 是最近一次被看见的
    逻辑时间。三个字段都是公开可读的，构造之后不再变化。
    """

    __slots__ = ("name", "alive", "last_seen")

    def __init__(self, name, alive=True, last_seen=0.0):
        self.name = name
        self.alive = bool(alive)
        self.last_seen = float(last_seen)

    def seen_at(self, moment):
        """返回把 last_seen 刷到 moment 后的新记录，存活标志不变。"""
        return MemberRecord(self.name, self.alive, moment)

    def snapshot(self):
        """返回这条记录的可序列化快照，用于节点之间整表交换。"""
        return {"name": self.name, "alive": self.alive, "last_seen": self.last_seen}

    def __repr__(self):
        return "<MemberRecord %s alive=%r last_seen=%r>" % (
            self.name, self.alive, self.last_seen)