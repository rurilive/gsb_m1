# archlite

内部备份工具用的 tar-lite 归档格式读写：512 字节块 + 头部字段 + 校验和，无压缩。纯标准库，无外部依赖。

## 格式

每个条目 = 512 字节头 + 数据（补零到 512 的倍数），归档以两个全零块结尾。头部：0-4 魔数 `ARCL`；4-68 名字（utf-8，NUL 补齐，最长 64 字节）；68-76 数据长度（大端 u64）；76-80 校验和（大端 u32，对校验和字段置零后的整个头部按字节求和）；80-512 全零填充。

## 对外 API（不可变更）

- `ArchiveEntry(name, data)`：`name`/`data` 属性，按值比较
- `pack_bytes(entries) -> bytes` / `unpack_bytes(blob) -> [ArchiveEntry]`
- `write_archive(path, entries)` / `read_archive(path) -> [ArchiveEntry]`
- `find_entry(blob, name) -> ArchiveEntry | None`：找不到返回 None；遇到坏归档也返回 None（恢复工具依赖的历史行为）

错误口径以 `tests/test_archlite.py` 为准（魔数/校验和/截断各自的文案逐字锁定）。打包时条目顺序保持不变，输出字节级确定（无时间戳等易变字段）。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 结构说明

- 两层：`writer.py` 只拼只写（`pack_bytes`/`write_archive` 共用 `iter_blocks`），`reader.py` 只读只解（`unpack_bytes`/`read_archive` 共用一个块扫描循环）；`archive.py` 仅作兼容门面导出原 API。
- 偏移与尺寸（0/4/68/76/80、块长、结束块数）与校验和算法唯一收在 `format.py`，`entry.py` 放 `ArchiveEntry` 及写入前校验；加版本字段只需改 `format.py` 与两处头处理。
- 错误分类：调用方给错类型抛 `TypeError`；归档畸形（截断/魔数/校验和）抛固定文案的 `ValueError`；坏名字透传 `UnicodeDecodeError`；文件层错误（如 `FileNotFoundError`）原样上抛；`find_entry` 吞掉 `ValueError` 返回 `None` 的历史行为不变。
