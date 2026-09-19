# shard

会话缓存集群的路由模块，单进程内嵌，纯标准库，无外部依赖。

## 现状

`shard/router.py` 提供统一的路由接口 `Router`（`add` / `remove` / `route`），目前唯一实现是取模路由 `ModuloRouter`：`md5(key) % N`。

## 问题

集群从固定 3 节点进入频繁扩缩容阶段。取模路由在节点数变化时，几乎全部 key 的归属都会变化（量化见 `python3 demo.py` 第二段统计），每次扩缩容缓存命中率被打穿，回源流量把数据库压得告警。

## 目标

见任务描述。约束：

- `ModuloRouter` 的行为保持不变（`tests/test_router.py` 是行为基线，一个字不改）
- 路由接口不变，新实现可无缝替换旧实现
- 纯标准库

## 运行

```bash
python3 demo.py                          # 现状演示 + 扩容迁移统计
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 环的存放：`_points`（升序哈希值）与 `_owners`（对应物理节点）两条对齐数组，由 `_rebuild` 在增删节点或调权重时重建。
- 虚拟节点：节点 `n` 的第 `i` 个虚拟节点哈希为 `md5("n#i")`，与 key 共用同一 md5 哈希空间。
- 查找：`bisect_right(_points, md5(key))` 找到顺时针第一个虚拟节点，越过环尾则绕回下标 0，取其 `_owners` 即目标节点。
- 权重：`set_weight(node, w)` 记录正整数权重，虚拟节点数 = 150 × w，权重 2 即 300 个虚拟节点、约双倍流量。
- 增删节点只影响环上相邻区间的 key，其余 key 归属不变，扩容迁移量约 1/N（见 demo.py 对比段）。
