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

## 问题

每条固定 16 字节，采集量上来以后文件膨胀得厉害；按时间定位只能从头扫，库越大扫得越久。

## 目标

见任务描述。约束：

- 现有行为与 `tests/` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 追加、顺序读出与定位演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 块压缩实现

- 新文件按块存：文件头 12 字节（魔数 `TSBLK01` + 块大小），每块 40 字节块头 + 变长块体，块大小由 `TsStore(path, block_size=10000)` 配。
- 块头记基准时间、末条时间、条数、块体长度、CRC32；时间戳在块体内按二阶差分 zigzag + LEB128 变长编码。
- 值先存首条 64 位原值，其余与前一条异或：为 0 写 1 个 0 位，否则写 1 位 + 6 位有效宽度 + 按宽度位打包。
- 打开时顺序扫块头建内存目录；`read_at` 只解所在块，`find` 走块头二分，都不把整库读进内存。
- 末尾未满的好块重开时读回内存继续攒；老裸存文件（`TSRAW01`）原样追加、格式不变、不迁移。
- CRC 不过或截断的块跳过，序号计入 `stats()["bad_blocks"]`，其余块照常读；`stats()` 另有 `decoded_blocks` 累计解块数。
