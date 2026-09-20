# auditchain

合规审计的追加型日志库，纯标准库，无外部依赖。

## 现状

`auditchain/log.py` 提供 `AuditLog`：

- `append(action, actor="", detail="", ts=None)` 追加一条，返回写进去的记录，带自增 `seq` 和内容摘要 `digest`
- `read_all()` 按写入顺序读回全部记录，`count()` 看条数，`last()` 看最新一条（返回的都是副本）
- 记录一行一条落在本地文件里；`auditchain/codec.py` 的规范编码把键序和分隔符定死，同一份内容在哪个进程里编出的字节都一样
- `auditchain/store.py` 的 `RecordStore` 管文件读写：追加走一把锁，扫描按文件顺序给出偏移，尾部没写完的半行跳过，中间出现解不开的行抛 `CorruptLogError`
- 摘要只覆盖内容本身，不改内容就算得出同一个摘要

## 问题

~~每条记录只跟自己绑，改掉一条没人看得出来，文件被截过也没人知道。~~ 已解决：每条记录带 `prev_digest`（上一条的摘要），`verify()` 沿链核对，改掉任何一条都会在链上露馅。

## 目标

`AuditLog.verify(deep=False)` 返回 `{"ok", "first_bad", "last_good", "checked"}`；默认从最近检查点起步往下核，`deep=True` 从第 1 条整链重核。约束：

- 现有方法与 `tests/` 里的基线行为保持不变（基线一个字不改）
- 纯标准库，装不了三方包

## 运行

```bash
python3 demo.py                            # 追加、读回、重开续写
python3 -m unittest discover -s tests -v   # 行为基线测试
```

## 实现说明

- 每条记录新增 `prev_digest`（第 1 条为空串），链指针参与 `digest` 摘要，改内容或改指针都会断链。
- `verify()` 逐行核对内容摘要、前链指针和 `seq` 连续性，`first_bad` 是第一处问题的记录号，`last_good` 是其前一条。
- 每 `checkpoint_every` 条（默认 1000）在 `<日志>.ckpt` 侧车文件固化 `seq/digest/offset` 及签名，只追加。
- 默认校验从最近一个签名有效的检查点锚点（含锚点）往下算，`checked` 是本次实算条数；`deep=True` 忽略检查点全量重核。
- 检查点之后整段被截断时，`first_bad` 报第一个缺失的号；手改或伪造的检查点签名失效，自动忽略并回退全核。
- 尾部没写完的半行打开时识别并截掉，`verify()` 只认到最后一个一致点，库不报废、可直接续写。
- 老日志（全部记录无链字段）打开时原子重写就地补链；只有部分记录缺字段的混合链不补，按篡改报出。
- 多线程 `append` 共用一把锁，链指针取锁内上一条的摘要，顺序严格跟随提交顺序，不分叉。
