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
`python3 -m unittest discover -s tests -v`）。共 23 个用例：15 绿、8 红。
红用例均为源码与本 README 语义约定的出入，逐条如下（括号内为对应缺陷与建议修复方向）：

- `test_max_height_scales_with_elements`、`test_random_height_distribution` 红：
  `_random_height` 的循环条件误写为 `h > _MAX_LEVEL`（恒为 False），节点高度恒为 1，
  跳表退化为普通链表，第 6 条分布不成立，这正是查询变慢的根源；
  建议把条件改为 `h < _MAX_LEVEL`。
- `test_duplicate_copies_coexist_in_insertion_order` 红：
  `_splice` 在同键前驱处直接 `continue`，后插的同键副本从未挂上 0 层链，
  违反第 1 条「恒新增副本」；建议去掉该跳过逻辑，让副本正常接到同键段末尾。
- `test_len_counts_each_copy_once`、`test_len_consistent_with_range_scan_on_duplicates` 红：
  `insert` 命中同键分支时 `_size` 多加一次，每插一个重复副本 `len()` 涨 2，
  违反第 4 条；建议删除同键分支里多余的那次 `_size += 1`。
- `test_remove_existing_key`、`test_remove_deletes_oldest_copy_only` 红：
  `remove` 只摘了 1 层及以上的指针，漏摘 0 层，节点仍挂在底层链上，
  导致删掉的键在 `range_scan`/`in` 中重新出现，违反第 2 条；
  建议补上 0 层前驱的指针摘除。
- `test_contains_with_none_value` 红：
  `__contains__` 用 `find() is not None` 判断，value 为 None 的副本被漏判，
  违反第 3 条「存在任一副本即命中」；建议改为独立判断目标节点是否存在，
  而非依赖 value 非 None。
