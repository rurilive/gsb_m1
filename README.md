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

## 防篡改链实现说明

- 每条记录新增 `prev` 字段挂上一条的 `digest`（首条挂 64 个 0），`digest` 覆盖 `prev`，改内容或改链都会对不上
- `verify(deep=False)` 返回 `{ok, first_bad, last_good, checked}`；默认从最近检查点起步，`checked` 是本次真算的条数；`deep=True` 整链重核
- 每 `checkpoint_every` 条（默认 1000）往 `<日志名>.chk` 追加一行 `{seq, digest}` 检查点；检查点之前的内容默认可信，出事用 `deep=True`
- 末尾没写完的半行校验时跳过；检查点越过文件末尾说明尾巴被截，自动整链重核并报出缺口位置 `first_bad`
- 老版本日志（无 `prev`）开库时就地补链：重算摘要、原子重写文件、补齐检查点，不拒绝打开
- 追加全程持锁，链顺序即提交顺序，多线程不分叉
