# regexlab

从字面量匹配起步的正则小库，纯标准库，Python 3.10+，无外部依赖。

## 现状

`regexlab/match.py` 只提供最朴素的字面量相等判断，模式里不认识任何
语法元字符：

- `LiteralMatch(pattern).test(text)`：输入串整段等于模式返回 `True`，否则 `False`
- `LiteralMatch(pattern).span(text)`：整段相等返回 `(0, len(text))`，否则 `None`
- `match(pattern, text)`：同样的整段相等语义，命中给出起止跨度，否则 `None`

模式里的点号、星号、方括号、圆括号、竖线这些符号目前都只当作普通
字符看待，没有字符类、没有量词、没有选择，也没有状态机。

## 目标

见任务描述。约束：

- `tests/test_match.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件，用固定模式与输入断言
- 纯标准库，异常继承 `RegexError` 基类

## 运行

```bash
python3 demo.py                          # 字面量匹配演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

（实现后补，10 行以内）
