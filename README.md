# unseal

zip 与 tar 的解包工具，纯标准库，无外部依赖。把归档摊到目标目录下，
条目按归档里的相对路径落，跑完给一份逐条流水加汇总。

## 用法

```python
from unseal import Extractor

report = Extractor("/srv/app/releases").run("build-1427.zip")
print(report.summary())
for item in report.results:
    print(item.relpath, item.action, item.reason)
```

- `Extractor(dest, max_entry_bytes=256*1024*1024, entry_source=iter_archive,
  chunk_size=65536)`
  - `run(archive)`：解一个归档，返回 `ExtractReport`；dest 不存在会建出来
  - `max_entry_bytes`：单条声明的解压尺寸上限
  - `entry_source`：条目来源，默认 `unseal.entries.iter_archive`，测试里
    可以换成合成的条目序列
- `ExtractReport`：`results` 是逐条 `EntryResult` 流水，`bytes` 是写出去
  的总字节数，另有 `written`、`dirs`、`links`、`skipped`、`rejected` 几个
  计数和 `summary()`
- `EntryResult`：`name` 是归档里原样的名字，`action` 是 write / mkdir /
  symlink / hardlink / skip / reject，`relpath` 是相对目标目录的 posix
  路径，`reason` 只在 reject 时有值，`size` 是这次写出去的字节数
- `iter_archive(path)`：按内容嗅探格式，返回 `Entry` 序列（zip 与 tar
  归一成同一套：`kind` 是 file / dir / symlink / hardlink / other，
  `declared_size` 是头部声明的解压尺寸，`linkname` 是链接目标）

`unseal/entries.py` 管归档读取，`unseal/extract.py` 管落盘编排，
两层都只吃标准库。

## 对拍工具

`unseal/reference.py` 是给测试用的判定基准与构造工具，线上路径别依赖它：

- `SafePlanner(dest, max_entry_bytes=...)`：只推演不落盘，按条目顺序给出
  每条该走什么动作、落到哪个相对路径、还是整条拒掉（`Verdict`，带理由码）；
  `run(archive)` 吃归档，`plan(entries)` 吃合成条目
- 理由码一套：`absolute-name`、`parent-component`、`backslash-name`、
  `empty-name`、`unknown-kind`、`case-collision`、`link-escape`、
  `conflicting-entry`、`missing-link-target`、`oversize`、`size-mismatch`
- `forge_zip(path, items)` / `forge_tar(path, items)`：按 `Forged` 列表拼
  归档，名字一个字节不改地写进去；zip 的 `declared` 能谎报普通文件的
  解压尺寸，软链、硬链、目录都能拼

## 运行

```bash
python3 demo.py                           # 现状演示
python3 -m unittest discover -s tests -v  # 行为基线测试
```
