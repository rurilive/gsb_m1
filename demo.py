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

    # 正则圈人 + 条件取反：企业邮箱域且非免费套餐才灰度
    regex_engine = compile_rules("""\
flag corp-beta
when and(email regex "^.*@corp\\.", not(plan eq free)) -> on
default off
""")
    print("=== corp-beta（regex + not）===")
    for label, ctx in [
        ("企业邮箱付费用户", {"email": "ada@corp.example", "plan": "pro"}),
        ("企业邮箱免费用户", {"email": "bob@corp.example", "plan": "free"}),
        ("外部邮箱付费用户", {"email": "cat@example.com", "plan": "pro"}),
    ]:
        decision = regex_engine.evaluate("corp-beta", ctx)
        print(decision.explain())
        print(f"  （{label}）\n")


if __name__ == "__main__":
    main()
