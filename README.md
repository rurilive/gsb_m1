# idemkey

支付链路的幂等键存储：按幂等键记住已处理请求的结果，同一个键再提交时
回放上次的结果，避免重复扣款。纯标准库，无外部依赖。

## 模块说明

`idemkey/store.py` 提供 `IdempotencyStore(ttl=None, clock=time.monotonic,
path=None)`：

- `begin(key)`：提交前问这个键要不要干活。返回 `True` 表示该由本次请求
  处理；返回 `False` 表示这个键已经处理过，调用方改用 `get(key)` 回放结果
- `finish(key, result)`：把处理结果记到键上，这个键之后就算已处理
- `get(key)`：取这个键已记下的结果，没有就返回 `None`
- `ttl`：记录存活秒数，`None` 表示永不过期
- `clock`：时间读取统一走它，便于测试注入
- `path`：记录落盘的文件路径，`None` 表示只放内存

记录字段：`result` 保存结果，`created_at` 是键被占上的时刻，`finished_at`
是收尾时刻。内部一把锁保护，磁盘读写也在锁内完成。

## 运行

```bash
python3 demo.py                          # 现象演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## Known Issues
