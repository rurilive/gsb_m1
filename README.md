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

每条记录只跟自己绑，改掉一条没人看得出来，文件被截过也没人知道。

## 目标

见任务描述。约束：

- 现有方法与 `tests/` 里的基线行为保持不变（基线一个字不改）
- 纯标准库，装不了三方包

## 运行

```bash
python3 demo.py                            # 追加、读回、重开续写
python3 -m unittest discover -s tests -v   # 行为基线测试
```
