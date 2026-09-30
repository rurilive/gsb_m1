"""exprparse.engine：改造前的朴素表达式工具。

所有能力都建立在一条路上——把表达式当成字符串，按运算符优先级从低到高反复扫描、
逐段切片、递归重建，再从最内层括号一层层剥开。没有词法单元化的记号概念，也没有
调度场或递归下降这类一趟走完的解析路径；字符串副本随括号层数成倍增加，一大就慢，
但结果是对的。

对外类 Expression 提供：

    evaluate(expr, variables=None)      中缀求值
    to_rpn(expr)                        中缀转后缀记号序列
    batch_evaluate(exprs, variables)    批量求值并给出最大值下标
    scan_count()                        上一次操作累计的字符串扫描次数

支持的二元运算符为加减乘除，除法是向下取整的整数口径；支持括号与一元负号。
后缀记号序列里，整数原样保留，二元运算符用其符号字符串，一元负号写作归类记号 u。
异常基类 ExprError，派生 InvalidSyntaxError、UnbalancedParenError、
DivisionByZeroError、UnknownVariableError、EmptyExpressionError。固定输入重复跑结果一致。
"""


class ExprError(Exception):
    """本包所有异常的共同基类。"""


class InvalidSyntaxError(ExprError):
    """运算符位置非法、数字串不合法、记号无法识别等。"""


class UnbalancedParenError(ExprError):
    """括号配对不合法。"""


class DivisionByZeroError(ExprError):
    """除数为零。"""


class UnknownVariableError(ExprError):
    """变量名不在取值表里。"""


class EmptyExpressionError(ExprError):
    """表达式为空串或整串空白。"""


_PRECEDENCE = {"+": 1, "-": 1, "*": 2, "/": 2}
_OPERATOR_CHARS = "+-*/"


class Expression:
    """朴素反复扫描式的中缀表达式工具。"""

    def __init__(self):
        self._scan = 0

    # ------------------------------------------------------------------ 计数

    def scan_count(self):
        """返回上一次操作累计的字符串扫描次数。"""
        return self._scan

    def _bump(self, n=1):
        self._scan += n

    # ------------------------------------------------------------------ 入口

    def evaluate(self, expr, variables=None):
        """中缀表达式求值，支持整数与变量两种取值口径，除法向下取整。"""
        self._scan = 0
        text = self._normalize(expr)
        return self._eval_segment(text, variables or {})

    def to_rpn(self, expr):
        """中缀转后缀（逆波兰）记号序列，只对纯数字表达式定义。"""
        self._scan = 0
        text = self._normalize(expr)
        return self._rpn_segment(text)

    def batch_evaluate(self, exprs, variables):
        """对一批表达式逐个求值，返回结果列表与最大值对应的下标。"""
        results = [self._eval_segment(self._normalize(e), variables or {})
                   for e in exprs]
        return results, self._argmax(results)

    @staticmethod
    def _argmax(values):
        if not values:
            raise EmptyExpressionError("批量求值的表达式列表为空")
        best = 0
        for i in range(1, len(values)):
            if values[i] > values[best]:
                best = i
        return best

    # ------------------------------------------------------------------ 归一

    def _normalize(self, expr):
        if expr is None or str(expr).strip() == "":
            raise EmptyExpressionError("表达式为空")
        text = "".join(str(expr).split())
        self._check_parens(text)
        return text

    def _check_parens(self, text):
        """整串括号配对预检，不合法直接快速失败。"""
        depth = 0
        for i in range(len(text)):
            self._bump()
            c = text[i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth < 0:
                    raise UnbalancedParenError("右括号多余")
        if depth != 0:
            raise UnbalancedParenError("左括号未闭合")

    # ------------------------------------------------------------------ 求值

    def _eval_segment(self, seg, variables):
        """在 seg 里从最低优先级运算符分段，递归下降；没有二元运算符就处理一元或原子。"""
        if seg.strip() == "":
            raise InvalidSyntaxError("空片段不能求值")
        pos = self._split_at_lowest(seg)
        if pos is not None:
            op = seg[pos]
            left = seg[:pos]
            right = seg[pos + 1:]
            if left == "" or right == "":
                raise InvalidSyntaxError("运算符两侧不能为空")
            if op == "+":
                return self._eval_segment(left, variables) + self._eval_segment(right, variables)
            if op == "-":
                return self._eval_segment(left, variables) - self._eval_segment(right, variables)
            if op == "*":
                return self._eval_segment(left, variables) * self._eval_segment(right, variables)
            divisor = self._eval_segment(right, variables)
            if divisor == 0:
                raise DivisionByZeroError("除数为零")
            dividend = self._eval_segment(left, variables)
            return dividend // divisor
        # 顶层没有二元运算符，可能是一元前缀、括号包住或原子
        if seg[0] in "+-":
            rest = seg[1:]
            if rest == "" or rest[0] in "*/":
                raise InvalidSyntaxError("运算符位置非法")
            self._bump()
            value = self._eval_segment(rest, variables)
            return -value if seg[0] == "-" else value
        inner = self._strip_one_paren(seg)
        if inner is not None:
            if inner.strip() == "":
                raise InvalidSyntaxError("括号内为空")
            return self._eval_segment(inner, variables)
        return self._eval_atom(seg, variables)

    def _split_at_lowest(self, seg):
        """返回顶层里优先级最低的那个二元运算符的位置，同级取最后出现处保证左结合。"""
        for level in (1, 2):
            pos = self._last_toplevel(seg, level)
            if pos is not None:
                return pos
        return None

    def _last_toplevel(self, seg, level):
        """扫一遍 seg，返回顶层里优先级等于 level 的最后一个二元运算符位置。

        括号内的字符跳过；紧跟在运算符或左括号之后的符号算一元前缀，不算二元运算符。
        """
        depth = 0
        found = None
        for i in range(len(seg)):
            self._bump()
            c = seg[i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth < 0:
                    raise UnbalancedParenError("右括号多余")
            elif depth == 0 and c in _PRECEDENCE and _PRECEDENCE[c] == level:
                if i > 0 and seg[i - 1] not in _OPERATOR_CHARS + "(":
                    found = i
        return found

    def _strip_one_paren(self, seg):
        """若整段被一对配对括号包住，返回内部串；否则返回 None。"""
        if not (seg.startswith("(") and seg.endswith(")")):
            return None
        depth = 0
        for i in range(len(seg)):
            self._bump()
            c = seg[i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0 and i != len(seg) - 1:
                    return None
        if depth != 0:
            raise UnbalancedParenError("左括号未闭合")
        return seg[1:-1]

    def _eval_atom(self, seg, variables):
        """取一个原子：非负整数或变量名。"""
        if seg.isdigit():
            self._bump(len(seg))
            return int(seg)
        if seg.isidentifier():
            self._bump(len(seg))
            if seg not in variables:
                raise UnknownVariableError("未知变量 " + seg)
            return variables[seg]
        raise InvalidSyntaxError("无法识别的记号 " + seg)

    # ------------------------------------------------------------------ 转后缀

    def _rpn_segment(self, seg):
        """朴素：反复扫描剥离优先级最低的顶层运算符，把它搬到序列末尾。"""
        pos = self._split_at_lowest(seg)
        if pos is not None:
            op = seg[pos]
            left = seg[:pos]
            right = seg[pos + 1:]
            if left == "" or right == "":
                raise InvalidSyntaxError("运算符两侧不能为空")
            return self._rpn_segment(left) + self._rpn_segment(right) + [op]
        if seg[0] in "+-":
            rest = seg[1:]
            if rest == "" or rest[0] in "*/":
                raise InvalidSyntaxError("运算符位置非法")
            self._bump()
            marks = ["u"] if seg[0] == "-" else []
            return self._rpn_segment(rest) + marks
        inner = self._strip_one_paren(seg)
        if inner is None:
            return self._rpn_atom(seg)
        if inner.strip() == "":
            raise InvalidSyntaxError("括号内为空")
        return self._rpn_segment(inner)

    def _rpn_atom(self, seg):
        if not seg.isdigit():
            raise InvalidSyntaxError("后缀序列只支持非负整数表达式")
        self._bump(len(seg))
        return [int(seg)]
