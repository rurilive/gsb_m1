# mqdp

窗口约束动态规划工具集，纯标准库，无外部依赖。

## 现状

mqdp/tables.py 提供一份朴素但正确的实现 WindowDP：一维状态转移里，每个
前缀把允许前驱区间内每个前驱挨个看一遍，取转移值的最小或最大，规模一大
就慢。

- WindowDP(window, coef, policy)：构造时校验窗口长度、转移系数与转移口径
- forward(terms)：正序逐前缀枚举前驱，返回前缀值表，长度等于项数加一
- steps(terms)：每个前缀选中的前驱下标表，并列时取下标较小者
- window_scan(terms)：另起一条独立做法，把窗口完整切片出来再逐个枚举
- matches(terms)：逐前驱表与独立窗口枚举表是否逐项一致
- answer(terms)：末尾前缀值，空序列返回零
- compare_count(size)：逐前驱枚举在给定规模下的转移比较次数
- window 取正整数，coef 取整数，policy 取 min 或 max

异常统一挂在 mqdp.tables.MqdpErro 之下（也可从包根 mqdp 导入）：
WindowErro、CoefErro、DataErro。

## 问题

每个前缀都要把前驱区间从头走一遍，窗口一滑就整段重算：窗口长度为一的
平凡情形也不做优化，比较次数长成规模的平方。序列长时重复劳动成倍放大，
始终停在朴素口径上，没有双端队列维护滑窗最优、队首出窗口、队尾按单调性
弹出劣解这些走法，新老两条路也没有相互印证。

## 目标

见任务描述。约束：

- tests/test_tables.py 是基线，一字不许改且必须全绿
- 新行为另开测试文件
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
