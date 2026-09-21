# tstore

把时序点按到达顺序存进本地文件的小仓，纯标准库，无外部依赖。

## 现状

`tstore/store.py` 里的 `TsStore` 按条裸存一个 (时间戳, 值) 序列：

- `TsStore(path)`：文件不存在就新建，已存在就接着写
- `append(ts, value)` / `append_many(pairs)`：时间戳只许不减，等于上一条可以，回退抛 `OutOfOrderError`；`append_many` 先校验整批，有一条不合法整批拒绝，文件不动
- `read_at(index)`：按下标读一条，支持负数下标，越界抛 `IndexError`
- `find(ts)`：第一个时间戳不小于 `ts` 的下标；重复时间戳返回整段里最早的那条，没有则返回 -1
- `read_all()` 与迭代：按写入顺序流式读出，同一句柄上刚追加的数据立刻可见
- `stats()`：`records` / `bytes_on_disk` / `appends` / `reads` 快照
- `close()` 与 with 语句，句柄可重复关闭

磁盘布局在 `tstore/layout.py`：8 字节魔数头加定长 16 字节记录（大端 int64 时间戳、float64 值），条数由文件长度推出，头部另做校验，长度对不上或魔数不对抛 `TsFormatError`。

## 块压缩实现

- 新文件用块压缩格式（魔数 `TSBLK01`），老裸存文件原样打开、原样追加，不迁移
- 块定条数，`TsStore(path, block_size=...)` 可配（默认 256）；块头 28 字节记基准时间、末条时间、条数、负载长度与 CRC32
- 块内时间戳对基准取差后做二阶差分，zigzag 加 LEB128 变长编码；值与前一条 float64 位型异或，为 0 写 1 比特，否则按前导零与有效位打包
- 打开只扫块头建索引，不整库进内存；`read_at`/`find` 按块头二分定位，只解所在块
- `stats()` 新增 `blocks_decoded`（累计解块数）与 `bad_blocks`（坏块序号）；校验不过或截断的块跳过继续读
- 一万条等间隔带抖动、低分辨率示数的点平均每条压到 5 字节内（`tests/test_blocks.py` 实测）

## 运行

```bash
python3 demo.py                          # 追加、读出、定位与块压缩演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
