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

## 预共享字典

`msglz/dict.py` 解决这个问题：

- `train_dictionary(samples, max_size)`：多定长 n-gram 计数找高频
  片段，顺着出现位置向右贪心延长，在 `max_size` 预算内全局按价值
  贪心装字典；最强片段放字典末尾（命中偏移更短）。纯标准库。
- `DictStore(dir, max_versions=4, min_gain=0.05, max_size=4096)`：
  磁盘上的多版本字典仓库，本身也是编解码器：
  - `rollout(samples)`：样本 80/20 切成训练集与评测集，训出新字典后
    只在没见过的评测集上实测帧长（含帧头与版本号）；比现役（没有
    现役时比无字典）好出至少 `min_gain` 才上线，否则现役原样退回。
    报告含是否上线、版本号、训练耗时、字典体积、双方总量/比率/收益
    与原因。
  - `encode/decode`：有现役字典就发种类 2 的帧（payload 第一个
    varint 是字典版本号），解码按版本取同一本字典；种类 0/1 的无
    字典老帧照常能解。
  - 多版本共存，超 `max_versions` 淘汰最老版本及其文件；帧头版本
    从未上线或已淘汰时抛 `DictVersionError`（异常带 `version`），
    绝不拿别的版本硬解；原文长度与 FNV 校验不过抛 `FormatError`。
  - 没有现役字典时 `encode` 发出的字节与 `MessageCodec` 完全一致。

实测（`demo.py`，约百字节的总线消息）：无字典比率约 1.09（越压越
大），带字典约 0.66，编码总量省约 39%；一万条训练约 3 秒。

约束：现有行为与 `tests/` 基线保持不变（基线一个字不改）；纯标准库。

## 运行

```bash
python3 demo.py                          # 短消息逐条压缩的尺寸与比率
python3 -m unittest discover -s tests -v # 行为基线测试
```
