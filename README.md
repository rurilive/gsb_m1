# suffixarr

字符串后缀数组与最长公共前缀的朴素工具，纯标准库，无外部依赖。

## 现状

suffixarr/suffix.py 提供朴素后缀工具 NaiveSuffix：

- NaiveSuffix(text)：在一段不可变字符串上做查询，text 属性取原文，len 取长度
- suffix_array()：把全部后缀切片取出后整体排序，返回排序后的起始下标序列
- lcp_of(i, j)：逐对后缀从头逐字符比较，求两后缀的最长公共前缀长度
- count_pattern(pattern)：逐个起始位置切出等长子串比较，统计模式出现次数
- count_distinct_substrings()：两层切片把全部子串塞进集合去重后计数
- longest_repeated_substring()：枚举每一对后缀求最长公共前缀，取其中最长者
- compare_count()：把排序口径下的字符比较次数如实报出来，作为可比对的代价
- SuffixError 是所有错误的基类，越界下标抛其子类，参数类型不对抛 TypeError

这些路径规模一大就明显变慢，但结果正确。

## 问题

后缀数组要把每一个后缀整体拿出来排一遍，比较是平方级的；任意两后缀的
最长公共前缀每次都得从头逐字符比过去；子串去重先吃下一大块内存；模式
出现次数只能一个位置一个位置地线性扫。文本一旦长起来，这几条路都撑不住。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_suffix.py 基线一致（基线一个字不改，须全绿）
- 新行为另开测试文件，不复用朴素路径的结论冒充新实现的验证
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

（实现后补，10 行以内）
