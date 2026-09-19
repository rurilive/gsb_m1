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

- 环由两条对齐的有序列表表示：哈希位（`bisect` 维护升序）与其归属的物理节点名。
- 虚拟节点位置为 `md5("{node}#{replica_index}")`，默认每物理节点 150 个。
- `route`：二分找 key 哈希顺时针第一个虚拟节点（`bisect_right`），越过环尾回到首位；环空抛 `KeyError`。
- 权重为正整数，虚拟节点总数 = `150 × weight`；`set_weight` 按 replica 下标增量增删，可随时调整。
- 增删节点或改权重只增删该节点对应的虚拟节点，故只有受影响环段的 key 换归属。
