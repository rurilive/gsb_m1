# splay

用一个 Python 列表维护一段整数序列的小工具，纯标准库，无外部依赖。

## 现状

splay/seq.py 只有一个朴素实现，Seq 直接在底层列表上操作：

- get(pos)：取第 pos 个元素，直接下标
- reverse(lo, hi)：截出该段、切片反序、再拼回原列表
- sum(lo, hi)：对截出的子列表逐个累加
- assign(lo, hi, value)：对每个位置逐个写一遍
- min(lo, hi) / max(lo, hi)：对截出的子列表逐个比较

没有树、没有分层结构，每次操作都整段拷贝或逐元素重排，序列一长
就退化成线性甚至平方。

## 问题

重复的区间操作每次都从头重算，压不下代价；没有一条按需上旋、把
均摊代价压下来的路径；也没有独立的朴素路径与原路径逐项对照。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_seq.py 基线一致（基线一个字不改）
- 新行为另开测试文件
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

（实现后补，10 行以内）
