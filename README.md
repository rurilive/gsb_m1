# msglz

消息总线上短消息的压缩库，纯标准库，无外部依赖。

## 现状

一条消息编成一个自包含的帧（`msglz/frame.py`：魔数 + 种类 + 原文长度 +
压缩体 + 原文的 FNV-1a 校验和），收端拿到帧就能解。压缩核在
`msglz/lz.py`，字节级 LZ77 自己实现，token 流是字面段与命中段两种；
压完比原文大就落回原文直存，帧头不变。

`msglz/codec.py` 里的 `MessageCodec`：

- `encode(data)`：把 bytes 编成一个帧，帧内自带原文长度与校验和
- `decode(frame)`：解回原文；魔数不对、长度对不上、校验不过一律抛
  `FormatError`，坏帧不会解出半截数据
- `stats()`：`messages` / `raw_bytes` / `encoded_bytes` / `decoded` /
  `ratio` 快照

压缩核另有一个 `preset` 参数：`compress(data, preset=b"...")` 允许命中
一段前置历史，`decompress(blob, preset=...)` 得拿同一段历史才能还原。
目前 `MessageCodec` 每次都用空 preset，没人在生产上用这个参数。

`demo.py` 里的 `make_corpus(count, seed)` 造一批总线短消息（字段名固定、
取值每次都换），当前演示是逐条压缩的实际尺寸与比率。

## 问题

短消息大都在百来字节上下，逐条独立压缩时字典积累不起来，帧头一摊，
压完常常比原文还大（demo 里的比率大于 1）。

## 目标

见任务描述。约束：

- 现有行为与 `tests/` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 短消息逐条压缩的尺寸与比率
python3 -m unittest discover -s tests -v # 行为基线测试
```
