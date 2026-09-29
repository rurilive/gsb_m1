# skippy

检索侧的有序映射，纯标准库，无外部依赖。

## 现状

skippy/sortedmap.py 提供 SortedMap，排序数组加旁路字典：

- m[key] = value：插入或覆盖，新键返回 True、覆盖返回 False
- m[key] / get(key, default)：按键取值，前者缺键抛 KeyError
- del m[key]：按键删除，缺键抛 KeyError
- range(lo, hi)：扫描左闭右开区间 [lo, hi)，返回按键升序的 (key, value) 列表
- keys() / items() / first() / __contains__ / __len__

## 问题

查找靠 bisect 是 O(log n)，但插入与删除都要把数组后半段整体搬移，是 O(n)。
键规模化之后增删是瓶颈。区间只能整段扫，没有按排名定位的能力，也没有可以先
定层再搜索的多层索引；插入顺序完全不参与结构，谈不上可复现的层高，更没有
当前层数、期望层高这类自洽的统计。

## 目标

在现有基础上扩出有序映射的跳表，支持范围、排名与确定性随机，见任务描述。约束：

- 现有行为与 tests/test_sorted.py 基线保持一致（基线一个字不改）
- 纯标准库
- 任意增删序列后有序迭代与 SortedMap 对拍一致，跳表只该换掉结构，不该改语义

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）