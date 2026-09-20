# vecpage

按版本维护的页表，纯标准库，无外部依赖。

## 现状

`vecpage/page.py` 提供一个 `PageTable`：

- `PageTable()`：空表，初始版本号为 0
- `map(page, frame, ver)`：把 page 在 ver 版本上映射到 frame
- `walk(page, ver)`：读出 page 在 ver 版本对应的帧，没有映射返回 None
- `unmap(page)`：取消 page 的映射，返回是否真的取消掉了
- `rollback(ver)`：把页表回滚到 ver 版本，丢掉该版本之后的记录
- `version()`：最近一次写入用到的版本号
- `MappingConflict`：同一页面在同一版本上被映射到不同帧时使用的异常类型

每个页面维护一串按版本号升序的 `(版本, 帧)` 记录，帧为 None 表示从该版本起
取消映射；`unmap` 产生的取消记录打在递增之后的新版本上。内部一把锁保护，
多路写入同时进来不会把表写坏。

## 问题

版本化页表上线后出现翻页错乱：按旧版本翻页翻到新帧、取消映射把历史版本一起
抹掉、回滚后页表项仍是新值、同页同版本的并发写入互相覆盖且不报冲突。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_page.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 翻页错乱现场复现
python3 -m unittest discover -s tests -v # 行为基线测试
```
