"""运行报告：逐节点终态、返回值、异常与耗时。"""


class RunReport(object):
    """一次 run 的账本。

    states 是节点名到终态的映射，顺序执行器跑完只会出现 "ok"；
    节点抛异常时先记 "failed" 再把异常抛给调用方。
    durations 是每个落地节点占用的墙钟秒数。
    attempts 是每个落地节点被执行的次数（含重试），由 Scheduler 记账。
    """

    def __init__(self):
        self.states = {}
        self.results = {}
        self.errors = {}
        self.durations = {}
        self.attempts = {}

    def status(self, name):
        return self.states[name]

    def ok(self):
        """全部落地节点都是 ok 才为真；空图无失败，算真。"""
        return all(state == "ok" for state in self.states.values())
