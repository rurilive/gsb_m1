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

## 块级增量传输（snapwire/transfer.py）

- `BlockIndex(block_size)` 是内容寻址块仓：`put` 按 sha256 存块、同内容
  只存一份、跨文件复用，`get`/`has` 按摘要取查，`stats()` 报存块数与字节数
- `Sender(index, channel)`：`plan(path)` 流式扫文件出块清单（只留摘要，
  内存不随文件涨）；`push(manifest)` 回应通道里的取块请求，只推接收端
  仓里缺的块，仓里没缓存就流式重读源文件按摘要匹配，一批最多 16 块
- `Receiver(index, channel)`：`apply(manifest, dst)` 收块校验入仓，校验
  不过只回请那一块；缺块发请求等下一轮，齐了写临时文件再 `os.replace`
  原子替换，失败与并发写都不留半截；dst 已是最新就直接收工不重写
- 断了重跑：已确认入仓的块不再请求也不再写，换条通道接着跑就补齐
- 对拍：随机改动下与 `sync_full` 结果逐字节一致，搬运量只跟改动范围走
