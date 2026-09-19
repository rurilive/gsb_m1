"""argmini 对外门面。

API 与历史版本完全一致，内部拆成三层：
- spec（spec.py）：add() 时把每个参数的 dest/action/取值方式定死；
- parse（parse.py）：只消费 token 流，产出 dict；
- render（render.py）：只把声明表画成帮助文本。

-h/--help 自动注册。解析失败抛 ArgsError，文本都被 tests 锁着。
"""

import sys

from argmini.errors import ArgsError
from argmini.parse import HelpRequested, parse_args
from argmini.render import render_help
from argmini.spec import Spec, SpecBook

__all__ = ["ArgsError", "Parser"]


class Parser(object):
    def __init__(self, prog, desc=""):
        self.prog = prog
        self.desc = desc
        self._book = SpecBook()

    def add(self, *names, **kw):
        """声明参数。names 里以 - 开头的是选项别名（可多个），其余是位置参数名。"""
        if not names:
            raise ValueError("add() needs at least one name")
        self._book.add(Spec.from_add(names, kw))
        return self

    def parse(self, argv):
        try:
            return parse_args(self._book, argv)
        except HelpRequested:
            sys.stdout.write(self.help())
            raise SystemExit(0)

    def help(self):
        return render_help(self._book, self.prog, self.desc)
