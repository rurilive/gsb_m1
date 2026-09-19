# exprx

规则引擎内嵌的表达式求值模块：词法 → 递归下降语法分析 → 求值，纯标准库。

## 语言语义

- 字面量：整数、小数；变量名：字母/下划线开头
- 运算符优先级（低 → 高）：`or` < `and` < 比较（`== != < <= > >=`）< `+ -` < `* / // %` < `^`（乘方，右结合）
- 一元负号：作用于整个乘方结果，`-2^2` 的值是 `-4`；`2^-3` 合法
- `and` / `or` 短路求值：左侧已能定值时右侧不求值，结果为布尔值
- `//` 与 `%` 是向下取整语义（与 Python 一致）：`-7 // 2 == -4`，`-7 % 2 == 1`
- `let x = e in body`：绑定仅在 body 内可见，退出后外层同名绑定不受影响，多次 evaluate 之间互不泄漏
- 除数为 0 时抛 `ZeroDivisionError`；引用未绑定变量抛 `NameError`

## 使用

```python
from exprx import Evaluator

ev = Evaluator()
ev.evaluate("let rate = 0.9 in amount * rate", {"amount": 80})
```

## 运行

```bash
python3 demo.py
```

## Known Issues
