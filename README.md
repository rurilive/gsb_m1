# bitag

广告后台的标签记录库：每条记录挂一组整数标签，查询用布尔表达式描述，
纯标准库，无外部依赖。

## 现状

`bitag/store.py` 的 `TagStore`：

- 记录 id 与标签都是 `[0, 2**32)` 的整数，`add(rid, labels)` 覆盖式写入（返回是否变更），
  `remove(rid)` 删除（返回是否删掉，删不存在的 id 是空操作）
- `get(rid)` 取记录的标签元组，`ids()` / `labels()` / `count()` 看全局，
  `postings(label)` 给标签命中的记录 id 集合（副本），`stats()` 给计数
- 倒排表是 `label -> set(rid)`，某个标签一个记录都不剩时当场删掉，不留空壳
- `subscribe(cb)` 登记变更回调 `cb(rid, old, new)`，`old` / `new` 是变更前后的标签元组，
  记录原本不存在或已被删除时给 `None`，只有真实变更才回调

`bitag/query.py`：

- 表达式节点 `Tag` / `And` / `Or` / `Not` / `Diff`，`parse("3&(7|~9)")` 从文本建树
- `evaluate(node, engine)` 求值，返回升序的记录 id 列表
- `SetEngine(store)` 是参考引擎，直接用 `set` 算，语义以它为准
- 引擎协议：`postings` / `universe` / `intersection` / `union` / `difference` /
  `complement` / `size` / `materialize` / `stats`，照这个实现就能接进 `evaluate`

`bitag/measure.py` 给内存口径：`deep_size(obj)` 按深遍历累加可达对象的实际占用，
共享对象只算一次；`human(n)` 把字节数写得好看点。

## 问题

倒排集合现在是 Python `set`。热门标签动辄几十万上百万个整数，一份 set 就是几十 MB，
两个大标签求交要按元素逐个探，查询一卡就是几十毫秒，内存也开始吃紧。

## 目标

见任务描述。约束：

- 现有行为与 `tests/` 下的基线保持不变（基线一个字不改）
- 纯标准库，运行环境没有网络

## 运行

```bash
python3 demo.py                          # 写入、覆盖写、布尔查询与占用口径演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
