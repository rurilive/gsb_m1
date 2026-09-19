# cachebox

规则引擎中间结果的进程内缓存，纯标准库，无外部依赖。

## 现状

`cachebox/cache.py` 提供固定容量的 `LRUCache`：

- `LRUCache(capacity, clock=time.monotonic)`：capacity 为最大条目数，clock 为注入时钟
- `set(key, value)` / `get(key)`（未命中返回 None）/ `delete(key)`（返回是否删掉）
- `stats()` 返回 `hits` / `misses` / `evicted` 计数快照
- 容量满时写入按 LRU 顺序驱逐最久未使用的条目；同 key 重复写入只覆盖值并刷新位置
- 内部一把锁保护，多线程单操作安全

## 问题

一部分 key 的旧值只有几分钟有效期，过期判断散落在各调用点，读前比对时间戳漏判即脏读。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_cache.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 容量驱逐演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 过期判定时机：`get` 读到条目时、`purge_expired()` 调用时、以及 `set` 写入后容量超限时，统一用注入的 `clock()` 与 `expires_at` 比对（`now >= expires_at` 即过期）
- `set(key, value, ttl=None)`：`ttl=None` 永不过期；同 key 重复 `set` 覆盖值并按新 ttl 重算过期时刻
- 与容量驱逐的先后：`set` 后容量超限时，先过滤全部过期条目（计入 `expired`），仍超量才按 LRU 驱逐最久未使用条目（计入 `evicted`）
- `get` 读到过期条目视同未命中：顺手删除、记一次 `misses` 和一次 `expired`
- `expired` 记账口径：只统计因过期被清除的条目，无论由 `get`、`purge_expired()` 还是 `set` 的容量过滤触发；每条只计一次
