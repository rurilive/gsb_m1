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
