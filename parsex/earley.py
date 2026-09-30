"""parsex 的朴素实现（改造前基线）。

上下文无关文法用单字符符号表示：规则左部是一个非终结符字符，右部是一串字符，
右部里出现过的、又是某条规则左部的字符视为非终结符，其余视为终结符。

识别与解析只有最直白的一条路：回溯递归下降。对每一条文法规则逐一尝试它右部
的每一种展开，命中就前进，失败就退回换下一种展开，没有任何记忆化与去重，
输入一长代价就指数级上升。功能正确，规模一大就慢，对左递归文法还会陷进
无限递归。
"""


class ParsexError(Exception):
    """本库所有异常的基类。"""


class InvalidInputError(ParsexError, ValueError):
    """违反输入口径时抛出（文本非字符串、非终结符不存在、区间不合法等）。"""


class GrammarError(ParsexError, ValueError):
    """定义文法时口径不合法（规则为空、左部非单字符、右部非字符串等）。"""


class ParseNode:
    """解析树节点。

    终结符叶子没有孩子，symbol 就是那个终结符字符；非终结符节点 symbol 是
    左部字符，children 是它右部各符号对应子节点组成的元组（可能为空，
    对应右部为空的产生式）。
    """

    __slots__ = ("symbol", "children")

    def __init__(self, symbol, children=()):
        self.symbol = symbol
        self.children = tuple(children)

    def is_leaf(self):
        return not self.children

    def __eq__(self, other):
        if not isinstance(other, ParseNode):
            return NotImplemented
        return self.symbol == other.symbol and self.children == other.children

    def __repr__(self):
        if not self.children:
            return f"ParseNode({self.symbol!r})"
        return f"ParseNode({self.symbol!r}, {list(self.children)!r})"


def _check_text(text):
    """文本校验：必须是字符串。"""
    if not isinstance(text, str):
        raise InvalidInputError("输入文本必须是字符串")
    return text


def _check_symbol(name, symbol):
    """符号校验：必须是单个非空白字符。"""
    if not isinstance(symbol, str) or len(symbol) != 1 or symbol.isspace():
        raise GrammarError(f"{name}必须是单个非空白字符")
    return symbol


class Grammar:
    """上下文无关文法。

    Grammar(rules)：rules 是一串 (左部, 右部) 二元组，左部是单个非空白字符，
    右部是字符串（可以为空串，表示空产生式）。第一条规则的左部即开始符号。
    """

    def __init__(self, rules):
        if not isinstance(rules, (list, tuple)):
            raise GrammarError("文法必须由规则序列给出")
        if not rules:
            raise GrammarError("文法至少要有一条规则")
        parsed = []
        for item in rules:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise GrammarError("每条规则必须是 (左部, 右部) 二元组")
            lhs, rhs = item
            _check_symbol("规则左部", lhs)
            if not isinstance(rhs, str):
                raise GrammarError("规则右部必须是字符串")
            parsed.append((lhs, rhs))
        self._rules = tuple(parsed)
        self._start = parsed[0][0]
        ordered = []
        for lhs, _rhs in parsed:
            if lhs not in ordered:
                ordered.append(lhs)
        self._nonterminals = tuple(ordered)
        self._nt_set = frozenset(ordered)
        terminals = []
        for _lhs, rhs in parsed:
            for ch in rhs:
                if ch not in self._nt_set and ch not in terminals:
                    terminals.append(ch)
        self._terminals = tuple(terminals)

    def start(self):
        return self._start

    def rules(self):
        return self._rules

    def nonterminals(self):
        return self._nonterminals

    def terminals(self):
        return self._terminals

    def rules_for(self, lhs):
        _check_symbol("非终结符", lhs)
        if lhs not in self._nt_set:
            raise InvalidInputError(f"文法里没有非终结符 {lhs!r}")
        return tuple(rhs for name, rhs in self._rules if name == lhs)

    def __repr__(self):
        body = ", ".join(f"{lhs}->{rhs or '空'}" for lhs, rhs in self._rules)
        return f"Grammar({body})"


class BacktrackParser:
    """回溯递归下降的识别与解析（改造前基线）。

    accepts(text)：判断 text 能否由开始符号整个导出。
    parse(text)：给出一棵解析树（深度优先最先找到的那棵），不识别则 None。
    all_parses(text)：枚举全部解析树。
    count_parses(text)：解析树个数。
    matches(nt, text)：非终结符 nt 在 text 中所有可导出的子串区间。
    attempts()：最近一次调用里尝试过的非终结符展开次数，可与规模对照。
    """

    def __init__(self, grammar):
        if not isinstance(grammar, Grammar):
            raise InvalidInputError("需要传入 Grammar 实例")
        self._grammar = grammar
        self._attempts = 0

    def grammar(self):
        return self._grammar

    def attempts(self):
        return self._attempts

    def _match_symbol(self, sym, text, pos):
        """从 pos 起匹配一个符号，逐一产生 (终止位置, 子树) 的全部可能。"""
        if sym in self._grammar._nt_set:
            self._attempts += 1
            for rhs in self._grammar.rules_for(sym):
                for end, kids in self._match_seq(rhs, text, pos):
                    yield end, ParseNode(sym, kids)
        else:
            if pos < len(text) and text[pos] == sym:
                yield pos + 1, ParseNode(sym)

    def _match_seq(self, rhs, text, pos):
        """从 pos 起匹配右部整串，逐一产生 (终止位置, 子节点列表)。"""
        if not rhs:
            yield pos, []
            return
        for mid, first in self._match_symbol(rhs[0], text, pos):
            for end, rest in self._match_seq(rhs[1:], text, mid):
                yield end, [first] + rest

    def _derive_full(self, text):
        """开始符号能整个导出 text 的全部 (解析树)。"""
        start = self._grammar.start()
        for end, node in self._match_symbol(start, text, 0):
            if end == len(text):
                yield node

    def accepts(self, text):
        text = _check_text(text)
        self._attempts = 0
        for _node in self._derive_full(text):
            return True
        return False

    def parse(self, text):
        text = _check_text(text)
        self._attempts = 0
        for node in self._derive_full(text):
            return node
        return None

    def all_parses(self, text):
        text = _check_text(text)
        self._attempts = 0
        return tuple(self._derive_full(text))

    def count_parses(self, text):
        text = _check_text(text)
        self._attempts = 0
        total = 0
        for _node in self._derive_full(text):
            total += 1
        return total

    def matches(self, nt, text):
        _check_symbol("非终结符", nt)
        if nt not in self._grammar._nt_set:
            raise InvalidInputError(f"文法里没有非终结符 {nt!r}")
        text = _check_text(text)
        self._attempts = 0
        spans = []
        for start in range(len(text) + 1):
            for end, _node in self._match_symbol(nt, text, start):
                spans.append((start, end))
        spans.sort()
        return tuple(spans)
