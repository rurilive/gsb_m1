"""SQL 子集的词法与语法分析。

支持：SELECT cols FROM table [WHERE cond] [ORDER BY col [ASC|DESC]] [LIMIT n]
cond 是比较条件（col op 字面量，见 plan.Compare）经 AND/OR 与括号
任意嵌套的布尔表达式，AND 优先级高于 OR。
关键字大小写不敏感，表名/列名大小写敏感，保留字不能作标识符。
语法不符抛 ParseError。
"""

from qmini.plan import COMPARE_OPS, And, Compare, Or

_RESERVED = frozenset(["SELECT", "FROM", "WHERE", "ORDER", "BY", "ASC", "DESC", "LIMIT", "AND", "OR"])
_TWO_CHAR_OPS = (">=", "<=", "!=")


class ParseError(Exception):
    """SQL 不符合支持的子集。"""


def tokenize(text):
    """切成 (kind, value, pos) 序列，末尾固定 END。

    kind: KW/IDENT/NUMBER/STRING/OP/END，'-' 紧跟数字并入负数字面量。
    """
    tokens = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if text[i:i + 2] in _TWO_CHAR_OPS:
            tokens.append(("OP", text[i:i + 2], i))
            i += 2
            continue
        if ch in "=><*,()":
            tokens.append(("OP", ch, i))
            i += 1
            continue
        if ch == "'":
            end = text.find("'", i + 1)
            if end < 0:
                raise ParseError("字符串字面量缺少右引号：%r" % text[i:])
            tokens.append(("STRING", text[i + 1:end], i))
            i = end + 1
            continue
        if ch.isdigit() or (ch == "-" and i + 1 < n and text[i + 1].isdigit()):
            j = i + 1
            while j < n and (text[j].isdigit() or text[j] == "."):
                j += 1
            lit = text[i:j]
            if lit.count(".") > 1:
                raise ParseError("非法数字：%r" % lit)
            tokens.append(("NUMBER", float(lit) if "." in lit else int(lit), i))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            word = text[i:j]
            if word.upper() in _RESERVED:
                tokens.append(("KW", word.upper(), i))
            else:
                tokens.append(("IDENT", word, i))
            i = j
            continue
        raise ParseError("无法识别的字符 %r（位置 %d）" % (ch, i))
    tokens.append(("END", None, n))
    return tokens


class SelectStmt:
    """一条 SELECT 语句的解析结果，字段与各子句一一对应。"""

    def __init__(self, columns, table, where, order_by, desc, limit):
        self.columns = columns    # ["*"] 或列名列表
        self.table = table
        self.where = where        # Predicate（Compare/And/Or）或 None
        self.order_by = order_by  # 列名或 None
        self.desc = desc
        self.limit = limit        # 非负 int 或 None


class _Parser:
    """递归下降，逐子句消费 token 流。"""

    def __init__(self, tokens):
        self._toks = tokens
        self._i = 0

    def _peek(self):
        return self._toks[self._i]

    def _next(self):
        tok = self._toks[self._i]
        self._i += 1
        return tok

    def _at(self, kind, val):
        tok = self._peek()
        return tok[0] == kind and tok[1] == val

    def _expect_kw(self, word):
        kind, val, _ = self._next()
        if kind != "KW" or val != word:
            raise ParseError("期望关键字 %s，实际是 %r" % (word, val))

    def _expect_ident(self):
        kind, val, _ = self._next()
        if kind != "IDENT":
            raise ParseError("期望表名/列名，实际是 %r" % (val,))
        return val

    def parse(self):
        self._expect_kw("SELECT")
        columns = self._select_list()
        self._expect_kw("FROM")
        table = self._expect_ident()
        where = None
        if self._at("KW", "WHERE"):
            self._next()
            where = self._condition()
        order_by, desc = None, False
        if self._at("KW", "ORDER"):
            self._next()
            self._expect_kw("BY")
            order_by = self._expect_ident()
            if self._at("KW", "ASC") or self._at("KW", "DESC"):
                desc = self._next()[1] == "DESC"
        limit = None
        if self._at("KW", "LIMIT"):
            self._next()
            kind, val, _ = self._next()
            if kind != "NUMBER" or not isinstance(val, int) or val < 0:
                raise ParseError("LIMIT 需要非负整数，实际是 %r" % (val,))
            limit = val
        kind, val, _ = self._peek()
        if kind != "END":
            raise ParseError("语句末尾有多余内容：%r" % (val,))
        return SelectStmt(columns, table, where, order_by, desc, limit)

    def _select_list(self):
        if self._at("OP", "*"):
            self._next()
            return ["*"]
        cols = [self._expect_ident()]
        while self._at("OP", ","):
            self._next()
            cols.append(self._expect_ident())
        return cols

    def _condition(self):
        """WHERE 表达式：OR 在最外层，AND 次之，括号可改优先级。"""
        return self._or_expr()

    def _or_expr(self):
        node = self._and_expr()
        terms = [node]
        while self._at("KW", "OR"):
            self._next()
            terms.append(self._and_expr())
        return terms[0] if len(terms) == 1 else Or(terms)

    def _and_expr(self):
        node = self._bool_primary()
        terms = [node]
        while self._at("KW", "AND"):
            self._next()
            terms.append(self._bool_primary())
        return terms[0] if len(terms) == 1 else And(terms)

    def _bool_primary(self):
        if self._at("OP", "("):
            self._next()
            node = self._or_expr()
            if not self._at("OP", ")"):
                raise ParseError("条件缺少右括号")
            self._next()
            return node
        return self._comparison()

    def _comparison(self):
        column = self._expect_ident()
        kind, op, _ = self._next()
        if kind != "OP" or op not in COMPARE_OPS:
            raise ParseError("期望比较符，实际是 %r" % (op,))
        kind, value, _ = self._next()
        if kind not in ("NUMBER", "STRING"):
            raise ParseError("期望字面量，实际是 %r" % (value,))
        return Compare(op, column, value)


def parse(text):
    """解析一条 SELECT 语句，返回 SelectStmt。"""
    if not isinstance(text, str) or not text.strip():
        raise ParseError("空语句")
    return _Parser(tokenize(text)).parse()
