# dedupq

消息接入服务里的本地去重队列，单进程内嵌，纯标准库，无外部依赖。

## 模块

- `dedupq/queue.py`
  - `DedupQueue(ttl=60.0, clock=None)`：内存去重队列
    - `submit(msg_id, payload=None)`：新 id 入队返回 True，重复 id 丢弃返回 False
    - `peek()`：返回队首 `(msg_id, payload)`，不消费；空队列返回 None
    - `pop()`：取出并消费队首，空队列返回 None
    - `size()` / `len()`：待消费条数
    - `cleanup()`：按当前时钟清理过期去重记录
  - `FakeClock`：可 `advance()` 的手动时钟，供演示与测试注入

去重记录保留 `ttl` 秒，过期后同一 id 可再次入队。默认时钟为 `time.monotonic`。

## 运行

```bash
python3 demo.py
```

## Known Issues

