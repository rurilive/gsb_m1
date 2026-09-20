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

测试位于 `tests/test_skiplist.py`（标准库 unittest，固定 seed，可独立重复运行）：

```bash
python3 -m unittest discover -s tests -v
```

共 20 个用例：10 绿、10 红。红用例按缺陷归为三组，每个红用例上方注释
均标明「README 期望 / 实际发生」。

### 缺陷一：随机层高永不升层（对应 README 第 6、7 条）

- 红用例：`test_max_height_grows_with_size`、`test_quarter_of_nodes_reach_level_two`、`test_no_superlinear_scaling_from_10k_to_100k`。
- 缺陷：`_random_height` 的循环条件写成 `h > _MAX_LEVEL`，永不成立，
  所有节点高度恒为 1，跳表退化为单链表，查找/插入/删除退化为 O(n)，
  这正对应「查询越跑越慢」的现象。
- 修复方向：把循环条件改为 `h < _MAX_LEVEL`，恢复每层 1/4 概率升层、上限 16 层。

### 缺陷二：重复键副本不入链且计数翻倍（对应 README 第 1、4 条）

- 红用例：`test_insert_duplicate_keys_coexist_in_insertion_order`、`test_len_counts_each_copy_exactly_once`。
- 缺陷：insert 的重复键分支里 `_size` 多加一次（每次重复插入 +2），
  同时 `_splice` 遇到同键前驱直接跳过该层，导致新副本根本没入链——
  len 虚高、range_scan 缺副本。
- 修复方向：删掉重复分支里多余的 `_size += 1`，并修正 `_splice`
  让同键段末尾的第 0 层正常链接新副本。

### 缺陷三：remove 漏摘第 0 层（对应 README 第 2、3、4 条）

- 红用例：`test_remove_unlinks_key_completely`、`test_remove_deletes_oldest_copy_only`、`test_find_returns_none_after_last_copy_removed`、`test_len_consistent_with_scan_after_remove`。
- 缺陷：remove 只摘第 1 层及以上的指针，漏了第 0 层，节点仍挂在链上——
  返回 True 后 `__contains__` 仍为 True、range_scan 仍输出该键、
  len 与 scan 条数不一致，这正对应「删掉的键又冒出来」的现象。
- 修复方向：remove 中补上第 0 层的摘链（`cur.forward[0] = node.forward[0]`）。

### 对拍用例

- 红用例：`test_random_op_stream_matches_reference`（固定 seed 随机操作流
  与朴素参考实现对拍），暴露的出入即缺陷二与缺陷三，不再单列。
