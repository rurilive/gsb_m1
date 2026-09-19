# skiplist

检索侧内存有序映射，跳表实现，纯标准库。键为同类型可比较值（demo 用整数），
value 任意。非线程安全。构造时可传 `seed` 复现随机层级。

## 语义约定（以下为本模块的正式行为定义）

1. **insert(key, value)**：**恒新增一个副本，不覆盖既有副本**；同键副本按插入先后共存于链上，先插的在前。
2. **remove(key)**：存在副本时**恰移除最旧的一个并返回 True**；没有副本则返回 False，且不改动任何结构。移除之后，该键若已无副本，`__contains__` 必须为 False，range_scan 也不再输出它。
3. **find(key) / `in`**：存在任一副本即命中；find 返回最旧副本的 value，无副本返回 None。
4. **`len()`**：**等于副本总数**，与 `range_scan()` 的输出条数一致。
5. **range_scan(lo=None, hi=None)**：**闭区间 [lo, hi]**，按 key 非降序输出每个副本的 `(key, value)` 元组；lo/hi 为 None 表示该侧无界；lo 大于 hi 时返回空列表。
6. **层级分布**：新节点高度从 1 层起，每层以 1/4 概率再升一层，即 P(height ≥ k) = (1/4)^(k-1)，上限 16 层。**`max_height` 属性返回当前最大节点高度（空表为 0），供诊断用**；千级元素规模下 max_height 通常不低于 4 层。
7. 查找/插入/删除的 O(log n) 依赖第 6 条的分布成立。

## 运行

```bash
python3 demo.py
```

## 测试报告

测试位于 `tests/test_skiplist.py`（标准库 unittest，仓库根目录运行
`python3 -m unittest discover -s tests -v`）。共 26 个用例，17 绿 9 红；
全部用例显式传 seed，可独立重复运行，结果确定。红用例及对应缺陷如下：

1. `test_max_height_typical_at_thousand_scale`（对应第 6、7 条）：
   `_random_height` 的循环条件误写为 `h > _MAX_LEVEL`（应为 `h < _MAX_LEVEL`），
   所有节点恒为 1 层，跳表退化成单链表，查询/插入/删除退化为 O(n)——
   即"查询越跑越慢"的根源。修复方向：把循环条件改为 `h < _MAX_LEVEL`。
2. `test_remove_last_copy_clears_contains`、`test_remove_last_copy_clears_range_scan`、
   `test_remove_twice_second_returns_false`、`test_len_matches_range_scan_after_remove`
   （对应第 2、4 条）：`remove` 只摘除了 1 层及以上的前驱指针，漏摘第 0 层，
   被删节点仍挂在底层链上，于是删掉的键又被 `in`/`find`/`range_scan` 查出来，
   且 `_size` 与链上节点数不再一致。修复方向：记录并摘除第 0 层前驱指针
   （沿用 `_preds` 的 update 数组即可）。
3. `test_duplicate_copies_coexist_in_insertion_order`、`test_len_counts_duplicate_copies`
   （对应第 1、4 条）：重复键插入时，`_splice` 遇到同键前驱直接 `continue`，
   新副本根本没接进链；同时重复分支里 `_size` 多加了一次，副本没加上、
   计数却 +2。修复方向：`_splice` 去掉同键跳过逻辑（同键段末尾之后正常链接），
   并删掉重复分支里多余的 `_size += 1`。
4. `test_remove_oldest_copy_leaves_newer`（对应第 2、3 条）：上述第 2、3 两项
   缺陷的叠加表现——最旧副本未被摘除，find 仍返回它。修复方向：随第 2、3 项
   一并解决。
5. `test_contains_with_none_value`（对应第 3 条）：`__contains__` 用
   `find(...) is not None` 判断，value 为 None 的键被误判为不存在。
   修复方向：`__contains__` 改为独立的键存在性判断（沿层找到候选节点后
   只比较 key，不看 value）。
