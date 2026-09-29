# autolab

从朴素自动机模拟起步的小库，纯标准库，Python 3.10+，无外部依赖。

## 现状

`autolab/dfa.py` 只提供最朴素的自动机模拟，给定一张转移表和一个输入
串就逐字符往前走，最后只回答接受还是不接受：

- `NaiveDFA(transitions, start, accepts)`：转移表键为 `(state, symbol)`，
  值为到达状态；`start` 是初态；`accepts` 是接受态集合
- `NaiveDFA.step(state, symbol)`：单步转移，无可用转移返回 `None`
- `NaiveDFA.run(text)`：逐字符走完全程，返回最终状态或 `None`
- `NaiveDFA.accepts_str(text)`：停在接受态返回 `True`，否则 `False`

眼下的实现不认识任何运算概念：没有可达性清理，没有死状态消除，没有
等价类，没有最小化，没有补集，也没有乘积构造。

## 目标

见任务描述。约束：

- `tests/test_dfa.py` 行为基线保持不变（基线一个字不改）
- 新行为另开 `tests/test_automata.py`，用固定自动机断言
- 纯标准库，异常继承 `AutError` 基类

## 运行

```bash
python3 demo.py                          # 朴素模拟演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

（实现后补，10 行以内）
