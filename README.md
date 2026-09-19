# mvstore

配置中心的单机 KV 存储，纯标准库，无外部依赖。

## 现状

`mvstore/store.py` 提供 `Store`：

- `Store(path=None)`：不给 path 纯内存；给了 path 所有写操作追加为 JSON 行日志，重新打开同一 path 按文件序重放恢复
- `get(key)`（不存在返回 None）/ `put(key, value)` / `delete(key)`（返回是否真的删了）
- value 为任意可 JSON 序列化对象
- 内部一把锁保护，多线程单操作安全

## 问题

没有事务：两个线程对同一 key 做读-改-写，互相整体覆盖，更新无声丢失。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_store.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 读写与恢复演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- 快照：`begin()` 记下当前全局版本号作为事务快照；事务内 `get` 先查自己的写缓冲，未命中则取该 key 版本链中不超过快照版本的最新一条
- 版本链：每个 key 存 `[(提交版本号, 值/墓碑)]`，按版本升序；墓碑表示删除
- 冲突判定：`commit` 时写集中任一 key 的最后提交版本大于快照版本，抛 `ConflictError`，事务作废
- 版本推进：检测通过则全局版本号加一，写集整体以新版本号落链，并照旧追加 JSON 行日志；非事务写视为立即提交
- `rollback()` 丢弃写缓冲并释放快照
- `gc()`：每 key 保留最新版，外加每个活跃事务快照可见的最新一条；无活跃事务时每 key 只留最新版
