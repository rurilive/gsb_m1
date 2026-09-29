"""autolab 当前实现：逐个状态试跑的朴素自动机模拟器。

一个正经的自动机工具应当能从状态转移表出发做一系列运算：先做可达性
清理，再构造补集与乘积，再做等价类划分得到最小 DFA，还要能与正则
表达式互相转换、枚举接受串、判定两个自动机是否等价。本文件目前只是
一个占位实现：给定一张转移表和一个输入串，从初态出发逐字符往前走，
走到哪算哪，最后只回答接受还是不接受。

眼下的实现不认识任何运算概念：没有可达性清理，没有死状态消除，没有
等价类，没有最小化，没有补集，也没有乘积构造。
"""


class AutError(Exception):
    """autolab 中所有自动机相关异常的基类。"""


class NaiveDFA:
    """最朴素的 DFA 模拟器：逐个状态试跑，判断接受与否。

    transitions 是一张转移表，键为 (state, symbol) 二元组，值为到达的
    状态；start 是初态；accepts 是可迭代的接受态集合。整个结构只做
    逐字符推进，不做任何清理或化简。
    """

    def __init__(self, transitions, start, accepts):
        self.transitions = dict(transitions)
        self.start = start
        self.accepts = frozenset(accepts)

    def step(self, state, symbol):
        """从 state 读入 symbol，返回到达的状态或 None。

        None 表示这一步没有可用的转移，也就意味着该串被拒绝。
        """
        return self.transitions.get((state, symbol))

    def run(self, text):
        """从初态开始逐字符走完 text，返回最终停留在的状态或 None。

        中途某一步没有可用转移时立刻返回 None。
        """
        state = self.start
        for symbol in text:
            state = self.step(state, symbol)
            if state is None:
                return None
        return state

    def accepts_str(self, text):
        """走完 text 后停在接受态就算接受，否则不接受。"""
        final = self.run(text)
        return final is not None and final in self.accepts
