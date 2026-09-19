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
