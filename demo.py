"""effecteval 现状演示。

第一段：带变量的表达式的分词、解析与求值，看一遍优先级、括号与未定义变量定位。
第二段：预留的依赖失效与副作用重放演示位子（见文末注释）。
"""

from effecteval import EvalRuntimeError, ParseError, eval, parse, tokenize


def main():
    print("=== 算术表达式求值 ===")
    src = "base + 2 * (3 - 1)"
    print("  原文:", src)
    print("  token:", [(t.kind, t.text) for t in tokenize(src)])
    print("  语法树根类型:", type(parse(src)).__name__)
    print("  求值结果:", eval(src, {"base": 10}))
    print("  左结合 10 - 3 - 2 ->", eval("10 - 3 - 2"))
    print("  浮点除法 7 / 2 ->", eval("7 / 2"))
    print("  取模 17 % 5 ->", eval("17 % 5"))
    print("  一元负号 -(2 + 3) ->", eval("-(2 + 3)"))
    try:
        eval("1 / 0")
    except EvalRuntimeError as exc:
        print("  除零定位所在下标:", exc.index, "消息:", exc.message)
    try:
        eval("1 + total", {"x": 1})
    except EvalRuntimeError as exc:
        print("  未定义变量定位所在下标:", exc.index, "消息:", exc.message)
    try:
        eval("1 +")
    except ParseError as exc:
        print("  残缺表达式定位所在下标:", exc.index)

    # TODO(依赖失效与副作用重放): 求值上下文、依赖跟踪、记忆化与失效、副作用记录与
    # 重放、惰性短路、事务回滚、并发隔离都补齐后，在这里加一段演示：
    # 在同一个上下文里求值一段带外部效果的表达式，打印 effect 日志；
    # 改一个被依赖的变量，打印哪些结果失效、哪些结果与缓存原样保留；
    # 把日志重放到一个新上下文，打印重放结果与原始结果一致；
    # 再演示一处含除零的求值被回滚，日志回到出错前的样子。


if __name__ == "__main__":
    main()