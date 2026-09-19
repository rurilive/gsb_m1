"""argmini: 内部工具共用的命令行参数解析包。对外暴露 Parser 和 ArgsError。"""

from argmini.parser import ArgsError, Parser

__all__ = ["ArgsError", "Parser"]
