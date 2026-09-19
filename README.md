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
