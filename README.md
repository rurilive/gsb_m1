# snapwire

本地文件快照与同步小工具，纯标准库，无外部依赖。

## 现状

- `snapwire/hashing.py`：`hash_bytes(data)` 与 `hash_file(path, chunk_size)`，
  后者按块流式读取，不把文件整份读进内存
- `snapwire/snapshot.py`：`take_snapshot(root)` 扫目录建快照
  （点号开头的文件与目录跳过，路径统一用斜杠分隔），
  `compare_snapshots(old, new)` 按路径升序列出 added、removed、modified，
  同名同内容不算差异；`save_snapshot`、`load_snapshot` 负责 JSON 落盘与读回
- `snapwire/sync.py`：`Channel(limit=None)` 是内存传输通道，双侧可收发，
  `bytes_moved` 统计累计搬运字节数，limit 不为 None 时模拟线路中断；
  `sync_full(src, dst, channel, chunk_size)` 是整份搬运的参考实现，
  返回本次搬运字节数，通道中途断裂抛 `ChannelBroken`

整份同步的代价与文件大小成正比，改一个字节也要把整份搬一遍。

## 目标

见任务描述。约束：

- `tests/` 下的基线测试保持不变（基线一个字不改）
- 纯标准库，不引入三方依赖

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
