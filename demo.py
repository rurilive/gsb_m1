"""Executor 现状演示。

第一段：固定次数重试——一个前两次失败第三次成功的函数，看重试与返回。
第二段：预留的退避抖动与熔断演示位子（见文末注释）。
"""

from resilkit.executor import Executor, RetryExhausted


def main():
    print("=== 固定次数重试 ===")
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError(f"第 {len(calls)} 次失败")
        return "第三次成功"

    ex = Executor(retries=5)
    result = ex.run(flaky)
    print(f"  run(flaky) -> {result}，实际调用 {len(calls)} 次")

    def always():
        raise TimeoutError("连接超时")

    ex2 = Executor(retries=2)
    try:
        ex2.run(always)
    except RetryExhausted as exc:
        print(f"  全部失败 -> attempts={exc.attempts} last={exc.last!r}")

    # TODO(退避抖动与熔断): 指数退避加抖动、异常类型过滤、熔断器状态机
    # 与半开单试探、各状态与计数口径实现后，在这里加一段演示：
    # 注入假时钟与固定 seed，跑一条连续失败序列，看退避等待时长逐个变长且抖动可复现，
    # 再看熔断器从闭合到开路、冷却后半开放行一个试探、成功后闭合的全过程与计数变化。


if __name__ == "__main__":
    main()