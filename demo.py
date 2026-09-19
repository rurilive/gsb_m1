"""演示：把一组风控规则跑一遍求值器，观察各条规则的输出。"""
from exprx import Evaluator


def main():
    ev = Evaluator()
    checks = [
        ("基线", "0.8", None),
        ("负数幂", "-2^2", None),
        ("负数地板除", "-7 // 2", None),
        ("负数取模", "-7 % 2", None),
        ("作用域嵌套", "let x = 1 in (let x = 99 in x) + x", None),
        ("除零防护规则", "x != 0 and 10 / x > 2", {"x": 0}),
        ("费率规则", "let rate = 0.9 in amount * rate", {"amount": 80}),
        ("费率复用", "amount * rate", {"amount": 80}),
    ]
    for label, expr, variables in checks:
        try:
            value = ev.evaluate(expr, variables)
            print(f"[{label}] {expr!r} -> {value}")
        except Exception as exc:
            print(f"[{label}] {expr!r} -> 出错: {type(exc).__name__}: {exc}")
    print("演示结束")


if __name__ == "__main__":
    main()
