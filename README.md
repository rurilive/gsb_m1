# auditchain

合规审计的追加型日志库，纯标准库，无外部依赖。

## 现状

`auditchain/log.py` 提供 `AuditLog`：

- `append(action, actor="", detail="", ts=None)` 追加一条，返回写进去的记录，带自增 `seq` 和内容摘要 `digest`
- `read_all()` 按写入顺序读回全部记录，`count()` 看条数，`last()` 看最新一条（返回的都是副本）
- 记录一行一条落在本地文件里；`auditchain/codec.py` 的规范编码把键序和分隔符定死，同一份内容在哪个进程里编出的字节都一样
- `auditchain/store.py` 的 `RecordStore` 管文件读写：追加走一把锁，扫描按文件顺序给出偏移，尾部没写完的半行跳过，中间出现解不开的行抛 `CorruptLogError`
- 摘要覆盖除 `digest` 外的全部字段

## 防篡改链

- 每条记录新增 `prev`：首条为空串，其余等于上一条的 `digest`；`digest` 把 `prev` 也算进去，改中间一条就得重算后面全部摘要
- `verify(deep=False)` 从最近一个检查点往下核，返回 `ok / first_bad / last_good / checked`，`checked` 是这次真重算的条数；`deep=True` 从第 1 条起一条不漏，改掉的那条报它的序号
- 每 N 条（默认 1000，构造参数 `checkpoint_every`）在旁路文件 `<日志>.ckpt` 固化一个锚点（seq、digest、prev、offset）；deep 还会拿锚点对条数，认出被整段截掉的尾巴
- 尾部半行在打开时截到最后一个完整位置，库不报废；`last_good` 给出最后一个一致点
- 上一版没有 `prev` 的老日志打开时自动就地补链（临时文件 + 原子替换），补完与新链同构并续写
- 多线程 `append` 共用一把锁，`prev` 严格跟随提交顺序，不分叉

## 运行

```bash
python3 demo.py                            # 追加、读回、重开续写
python3 -m unittest discover -s tests -v   # 行为基线测试
```

## 实现说明

- 链字段 `prev` 计入规范编码，`digest=sha256(canonical(record 去掉 digest))`，首条 `prev=""`
- 检查点是旁路 JSON-lines 文件，只作加速与截尾对照，不是信任根；坏行跳过
- shallow 从 seq 最大且不超过现存条数的锚点起步（锚点本身也重算），无锚点则从头
- deep 全链重算，并把每个锚点的 digest/prev 与日志逐条对照；只改日志、重算全链但没同步 `.ckpt` 仍会在锚点处暴露
- 打开日志时先扫并截掉半行尾巴，再检测无 `prev` 的老记录并原子整文件重写补链，随后按新链重建检查点
- 纯标准库；十万条追加约 4 秒、deep 校验约 1.3 秒
