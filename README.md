# sufauto

子串统计工具包，纯标准库，无外部依赖。

## 现状

`sufauto/substat.py` 提供 `SubstringStats`，全部靠朴素枚举：

- `distinct_substring_count()`：枚举全部子串塞进集合去重
- `count_occurrences(pattern)`：枚举全部起点逐个比对，含重叠
- `contains(pattern)`：出现次数是否大于零
- `longest_repeated_substring()`：枚举全部子串、逐个再数一遍出现次数取最长
- `distinct_substrings()`：去重后升序的全部子串

## 问题

枚举全部起点与全部子串是平方量级，去重时每个子串还要切片与哈希，
整体接近立方量级。串长一上来，求不同子串个数就顶不住；出现次数、
最长重复子串、存在判断也都在重复做同样的枚举。线性做法目前一个都没有。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_substat.py` 基线保持一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

（实现后补，10 行以内）
