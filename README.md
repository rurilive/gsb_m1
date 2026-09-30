# radixlab

非比较排序的朴素实现，纯标准库，无外部依赖。

## 现状

`radixlab/radix.py` 提供 `NaiveRadix`：

- `load(values)`：载入一批非负整数，超过取值上限或含负数判非法
- `values()`：原始序列的副本，输入保持不变
- `width()`、`bit_width()`、`half_width()`：十进制位宽、二进制位宽、二进制半位宽
- `comparison_sorted()`：内置排序给出的非降序序列，作为对照基准
- `lowdigit_path()`：从低位到高位逐位分桶排序，结果与非降序一致
- `highdigit_path()`：按固定二进制位宽分两趟排序，结果与十进制位路径一致
- `digit_histogram(pos)`、`bucket_counts(pos)`：第 pos 位各数字出现的次数
- `modal_digit(pos)`：第 pos 位出现次数最多的数字，并列取较小者
- `is_sorted(sequence)`、`check_sorted()`：是否非降序
- `comparison_count()`、`placement_count()`、`reset_counts()`：两类规模计数

现状全部走最直白的路子：非负整数序列直接交给内置排序；按位分组时对每个元素反复
求它某一位上的数字；求第几位用循环除十逐次取余；众数与分桶也各跑一套逐元素的分组。
口径直白、结果确定，但规模一大就退化到依赖比较排序。异常基类是 `RadixError`，
输入不合法抛 `RadixInputError`。

## 问题

没有真正的计数分桶过程，看不出非比较排序不做元素间比较这一事实；十进制位路径靠
内置排序逐趟收回，二进制位路径也没有按位宽的稳定分摊；某位众数与分桶计数各写一套
逐元素分组，重复且低效；比较次数与分配次数无法与线性做法做规模对照。

## 目标

见任务描述。约束：

- `tests/test_radix.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py                          # 朴素实现演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

（实现后补，10 行以内）
