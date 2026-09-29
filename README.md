# hashring

把 key 稳定分片映射到节点的小库，纯标准库，无外部依赖。

## 现状

hashring/modulo.py 提供朴素取模分片 ModuloSharding：

- ModuloSharding(nodes=(), hash_fn=None)：建立一个分片表，nodes 是初始
  节点序列，hash_fn 是可注入的哈希函数，缺省用内置 md5
- add_node(node)：把一个节点追加到列表末尾，重复加入同一节点无副作用
- remove_node(node)：把一个节点从列表里摘掉，节点不存在时抛 KeyError
- lookup(key)：返回 key 取模后命中的节点，空表返回 None
- nodes()：表里的节点，按名字排序

key 的哈希对节点个数取模得到下标，每个物理节点在表里只占一个位置。

## 问题

取模分片的分母一变就全盘重排：增删一个节点，大多数 key 的取模结果都会
改变，归属大面积跳走，缓存与状态跟着失稳。节点能力不同却无法按容量分配
权重，负载只能听天由命；一个 key 也无法映射到多个节点做副本；分布是否
均衡没有任何度量手段。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_modulo.py 基线一致（基线一个字不改）
- 新行为另开 tests/test_ring.py
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
