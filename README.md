# strhash

字符串子串判定的朴素工具，纯标准库，无外部依赖。

## 现状

`strhash/strings.py` 提供 `NaiveStr`：

- `NaiveStr(text)`：在一段不可变文本上做查询，`text` 属性取原文，`len` 取长度
- `substr(start, end)`：按半开区间取子串切片，允许空区间
- `is_equal(a_start, a_end, b_start, b_end)`：判定两段子串是否相等，逐字符比较整段切片
- `lcp(i, j)`：两个后缀的最长公共前缀长度，从首字符逐个往下比
- `contains(pattern)` / `count_pattern(pattern)`：逐一位置切出等长切片与模式比较，计数含自重叠
- `count_distinct_substrings()`：两层切片把全部子串塞进集合去重后计数
- `is_rotation(other)`：拼接自串后逐位置整段比较，判定循环同构
- `compare_count(...)`：两段子串逐字符比较实际走到的字符比对次数
- `HashError` 是所有错误的基类，越界下标抛其子类，参数类型不对抛 `TypeError`

这些路径判定一多就是平方量级，文本一长就明显变慢，但结果正确且不依赖任何全局状态。

## 问题

要判定两个子串是否相等，就得把两段切片整体比较一遍；两个后缀的公共前缀
每次都从首字符重扫；子串出现与循环同构只能在每个起始位置整段对齐比对；
数不同子串更狠，全部子串先塞进集合再计数，时间与内存都是平方级。文本变
长后，这些判定同时扛不住，需要一套能在常数时间取任意子串哈希、并据以支撑
上述全部判定的结构。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_strings.py` 基线一致（基线一个字不改，须全绿）
- 新行为另开测试文件，不复用朴素路径的现成结论冒充新实现的验证
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

（实现后补，10 行以内）
