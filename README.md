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

- 每个 key 维护按版本号升序的多版本链 `(version, value)`，删除写 tombstone；全局版本号每次成功提交（事务或单操作）加一。
- `begin()` 以当前全局版本作为快照版本登记事务；事务 `get` 读快照时刻可见版本（自身缓冲写优先），`put/delete` 只落缓冲。
- `commit()` 对写集做 first-committer-wins：任一 key 的最后提交版本晚于本事务快照即抛 `ConflictError` 并作废缓冲；否则写集以同一新版本号生效，照旧逐 key 追加 JSON 行日志。
- `rollback()` 丢弃缓冲并注销事务。
- `gc()` 保留各活跃事务快照可见的版本与全局最新版，其余旧版本回收；无活跃事务时每 key 只留最新版，最新版是 tombstone 则连 key 清除。
- 重放旧格式（无 `ver`）日志时按文件序补版本号。
