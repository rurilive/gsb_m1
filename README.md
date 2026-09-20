# bufpool

网关侧拼装报文的进程内缓冲区分配器，纯标准库，多线程环境里跑。

## 现状

- `bufpool/tiers.py`：档位划分。`TIERS` 从 256 到 65536，`tier_of(size)`
  给出能装下请求的最小档位，超过最大档位返回 `None`；`check_size()` 校验请求容量，
  `tier_key()` 给统计口径的档位标签（超出最大档位的记 `oversize`）。
- `bufpool/buffer.py`：`Buffer` 包一段 bytearray。`size` 是请求容量，`capacity`
  是实际可用字节数，`capacity >= size`；`view()` 是整段可写视图，`zero()` 清零。
- `bufpool/stats.py`：`AllocStats` 记 acquire / release 次数、请求字节数、在借数量与峰值、
  按档位的 acquire 分布。
- `bufpool/alloc.py`：`Allocator` 每次 `acquire(size)` 新分配 bytearray，
  `release(buf)` 之后交给 GC。`clock` 可注入，用于记录借出时刻；
  `outstanding()` 看在借缓冲的持有秒数；释放不属于自己的缓冲抛 `UnknownBuffer`。

所有 `acquire` 回来的缓冲内容都是全零的，这是各分配器实现共用的可见语义。

## 目标

池化改造见任务描述，接口与既有语义以现状为准。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
