"""递归回溯的匹配执行与对外接口。

只处理 Char 与 Star：从 pos 起逐节点试着吃字符，量词按贪婪回溯。
文本一长、量词一嵌套，重试次数会指数级炸开；搜索是从每个起点把整棵树
重跑一遍，长文本上的代价直接和起点数相乘。
"""

from .parser import Char, Seq, Star, parse


class Match:
    """一次成功匹配，目前只知道整体区间。"""

    __slots__ = ("_text", "_start", "_end")

    def __init__(self, text, start, end):
        self._text = text
        self._start = start
        self._end = end

    def start(self):
        return self._start

    def end(self):
        return self._end

    def span(self):
        return (self._start, self._end)

    def group(self):
        return self._text[self._start:self._end]

    def __repr__(self):
        return "<Match %r %d:%d>" % (self.group(), self._start, self._end)


def _check_text(text):
    if not isinstance(text, str):
        raise TypeError("待匹配的文本得是字符串")


def match_from(ast, text, pos):
    """从 text[pos] 起匹配整棵树，成功返回结束下标，失败返回 None。"""
    if not isinstance(ast, Seq):
        raise TypeError("match_from 需要 parse 出来的 Seq 节点")
    return _match_seq(ast.children, 0, text, pos)


def _match_node(node, text, pos):
    return _match_seq((node,), 0, text, pos)


def _match_seq(nodes, index, text, pos):
    if index == len(nodes):
        return pos
    node = nodes[index]
    if isinstance(node, Char):
        if pos < len(text) and text[pos] == node.ch:
            return _match_seq(nodes, index + 1, text, pos + 1)
        return None
    if isinstance(node, Star):
        # 贪婪：先把子节点能多吃就多吃，再从最长到最短挨个试后续
        ends = [pos]
        end = pos
        while True:
            nxt = _match_node(node.child, text, end)
            if nxt is None or nxt == end:
                break
            end = nxt
            ends.append(end)
        for cand in reversed(ends):
            got = _match_seq(nodes, index + 1, text, cand)
            if got is not None:
                return got
        return None
    raise TypeError("不认识的节点：%r" % (node,))


def naive_search(ast, text):
    """朴素搜索：每个起点整棵树重跑，取第一个成功的位置。"""
    for start in range(len(text) + 1):
        end = match_from(ast, text, start)
        if end is not None:
            return Match(text, start, end)
    return None


class Pattern:
    """编译好的模式。构造时解析，语法出错抛 PatternError。"""

    def __init__(self, pattern):
        if not isinstance(pattern, str):
            raise TypeError("模式得是字符串")
        self.pattern = pattern
        self._ast = parse(pattern)

    def fullmatch(self, text):
        """整串匹配：从 0 开始吃，要求正好吃到串尾。"""
        _check_text(text)
        return match_from(self._ast, text, 0) == len(text)

    def search(self, text):
        """在 text 里找第一处匹配，找不到返回 None。"""
        _check_text(text)
        return naive_search(self._ast, text)

    def __repr__(self):
        return "<Pattern %r>" % self.pattern


def fullmatch(pattern, text):
    """整串匹配的快捷写法。"""
    return Pattern(pattern).fullmatch(text)


def search(pattern, text):
    """搜索的快捷写法。"""
    return Pattern(pattern).search(text)
