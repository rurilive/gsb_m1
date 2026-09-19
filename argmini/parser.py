"""argmini 对外门面。

内部分三层，本文件只负责接线，签名和行为保持 2017 年以来不变：

- spec 层（argmini.spec）：add() 时把 dest、takes_value、action 定死；
- parse 层（argmini.parse）：parse() 时只走 token 流；
- render 层（argmini.render）：help() 时只拼文本。

-h/--help 自动注册。解析失败抛 ArgsError，文本都被 tests 锁着。
"""

import sys

from argmini.parse import ArgsError, HelpRequested, parse_tokens
from argmini.render import render_help
from argmini.spec import SpecRegistry, make_help_spec, make_spec


class Parser(object):
    def __init__(self, prog, desc=""):
        self.prog = prog
        self.desc = desc
        # -h/--help 是自动注册的，一直挂在列表最前面
        self._specs = [make_help_spec()]

    def add(self, *names, **kw):
        """声明参数。names 里以 - 开头的是选项别名（可多个），其余是位置参数名。"""
        if not names:
            raise ValueError("add() needs at least one name")
        self._specs.append(make_spec(names, **kw))
        return self

    def parse(self, argv):
        registry = SpecRegistry(self._specs)
        try:
            return parse_tokens(registry, argv)
        except HelpRequested:
            sys.stdout.write(self.help())
            raise SystemExit(0)

    def help(self):
        return render_help(self.prog, self.desc, SpecRegistry(self._specs))
