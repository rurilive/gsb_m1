# ringbuf

多生产者/多消费者定长环形缓冲，网关进程内嵌使用，纯标准库（threading.Lock）。

## 语义

- `put(item)`：写入一个元素，永不阻塞；缓冲满时覆盖最老元素，count 不会超过容量
- `get()`：取出最老元素；缓冲为空时抛 `ringbuf.Empty`；每条消息只会被一个消费者取到
- `count()`：当前元素个数，取值范围 [0, capacity]
- `snapshot()`：按逻辑顺序（写入顺序）导出当前内容的副本，不影响缓冲状态
- 所有操作线程安全，可在多线程读写场景下直接使用

## 运行

```bash
python3 demo.py
```

## Known Issues
