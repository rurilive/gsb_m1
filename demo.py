"""flagr 演示：编译规则 -> 按上下文求值 -> 决策与解释。"""

from flagr import compile_rules

RULES = """\
# 网关灰度规则
flag checkout-v2
when and(country in [CN, US], plan eq pro) -> on
default off

flag beta-ui
when or(vip eq true, age ge 18) -> on
default off
"""

CONTEXTS = [
    ("cn-pro 请求", {"country": "CN", "plan": "pro", "vip": False, "age": 17}),
    ("us-vip 请求", {"country": "US", "plan": "free", "vip": True, "age": 30}),
    ("jp 新用户", {"country": "JP", "plan": "free", "vip": False, "age": 9}),
]


def main():
    engine = compile_rules(RULES)
    for flag in engine.flags:
        print(f"=== {flag} ===")
        for label, ctx in CONTEXTS:
            decision = engine.evaluate(flag, ctx)
            print(decision.explain())
            print(f"  （{label}）\n")

    # TODO(正则规则): regex 匹配器与 not() 组合器就位后，在这里加一条用正则
    # 圈定邮箱域的规则演示，展示命中与未命中两种解释输出。


if __name__ == "__main__":
    main()
