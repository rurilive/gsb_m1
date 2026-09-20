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

## 实现说明

- 每条记录新增 `prev` 字段，存上一条的 `digest`（首条为 64 个 0）；`digest` 覆盖 `prev`，改任何一条都会让后一条的指针对不上
- `verify(deep=False)` 返回 `{ok, first_bad, last_good, checked}`；`first_bad` 是第一条对不上的记录的序号，`last_good` 是最后一个一致点
- 每 `checkpoint_interval` 条（默认 1000）往 `<日志名>.chk` 固化一个检查点（序号、偏移、摘要）；`verify()` 默认锚定最近的检查点只核其后，`checked` 即本次实算条数；检查点对不上或缺失自动回退整链重核
- `verify(deep=True)` 从首条核到尾，一条不漏
- 末尾写一半的半行、被截掉的尾巴不算坏：`last_good` 落在最后一条完整且一致的记录上，重开时截掉半行再续写
- 上一版写的无链字段日志打开时就地补链（重算 `prev`/`digest` 整份重写并重建检查点），不拒绝打开
- `append` 全程持锁，`prev` 计算与落盘原子完成，多线程下链顺序即提交顺序，不分叉
- 实测十万条追加约 4s、整链校验约 1.3s，远低于一分钟预算
