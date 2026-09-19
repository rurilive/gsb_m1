"""开关引擎：按序求值规则链，产出决策与解释。

求值语义：
- 同一开关的 when 规则按书写顺序求值，第一条命中的立即定决策
- 全部未命中走 default；没写 default 视为 off
- 每次求值留下一份 trace：按序记录每条规则的序号、describe 与命中与否
"""

from .errors import UnknownFlagError


class Rule:
    """一条 when 规则：序号（1-based）+ 匹配器 + 命中后的决策。"""

    def __init__(self, index, matcher, enabled, line):
        self.index = index
        self.matcher = matcher
        self.enabled = enabled
        self.line = line


class FlagSpec:
    """一个开关的定义：when 规则链 + default。"""

    def __init__(self, name, line):
        self.name = name
        self.line = line
        self.rules = []
        self.default = False
        self.has_default = False


class Decision:
    """一次求值的结果。source: "rule#N" 或 "default"。"""

    def __init__(self, flag, enabled, source, matched, trace):
        self.flag = flag
        self.enabled = enabled
        self.source = source
        self.matched = matched
        self.trace = tuple(trace)

    def explain(self):
        lines = [f"{self.flag} -> {'on' if self.enabled else 'off'} ({self.source})"]
        for index, text, hit in self.trace:
            lines.append(f"  #{index} {text} {'hit' if hit else 'miss'}")
        return "\n".join(lines)


class FlagEngine:
    """编译产物：开关定义集合 + 求值入口。"""

    def __init__(self, specs):
        self._specs = {}
        for spec in specs:
            self._specs[spec.name] = spec

    @property
    def flags(self):
        return list(self._specs)

    def spec(self, flag):
        return self._specs[flag]

    def evaluate(self, flag, ctx):
        """对上下文求值，返回 Decision。未定义的开关抛 UnknownFlagError。"""
        spec = self._specs.get(flag)
        if spec is None:
            raise UnknownFlagError(flag)
        trace = []
        for rule in spec.rules:
            hit = rule.matcher.matches(ctx)
            trace.append((rule.index, rule.matcher.describe(), hit))
            if hit:
                return Decision(flag, rule.enabled, f"rule#{rule.index}",
                                rule.index, trace)
        return Decision(flag, spec.default, "default", None, trace)
