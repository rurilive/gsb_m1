# slidewin

滑动窗口与双指针统计工具包，纯标准库，无外部依赖。

## 现状

slidewin/window.py 提供 WindowStats：

- sum_bounds(seq, target)：返回 SumReport，含和不小于目标的最短子数组长度与和不大于
  目标的最长子数组长度，没有满足条件的段时对应长度取零
- longest_distinct(text, cap)：返回 DistinctReport，给至多含 cap 个不同字符的最长子串
  的长度与左端，无解时长度为零、左端为负一
- distinct_count(text, cap)：恰好含 cap 个不同字符的子串个数，走至多相减的口径
- cover_window(text, target)：覆盖全部目标字符的最短窗口，返回左右端点与长度三元组，
  无解时为负一负一零
- last_scan：本次调用扫描过的元素总次数
- SlideErro：异常基类，下分 SeqErro 与 ParamErro

## 问题

四条路都靠枚举全部窗口，再对每个候选窗口从头重新求和、重新统计不同字符数、重新检查
覆盖情况，窗口一多就是平方量级，每个窗口再从头重扫一遍就退化成立方量级。基线既拿不出
任何访问计数说明更聪明的做法省了多少，新老两条路也无从相互印证，空串、单字符、无满足
条件的窗口、整串恰为答案、目标为零、含重复字符这些边界只能靠肉眼去猜。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_window.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
