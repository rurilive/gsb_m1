# b85x

消息网关用的流式编解码包，纯标准库。Base85 用 RFC 1924 字符表，Base32 用
RFC 4648 字符表与位序。所有编解码器都是流式的：数据可以按任意边界分块喂入，
最终结果与一次性处理整段输入完全一致。

## 语义约定（以下为本模块的正式行为定义）

1. **通用**
   - 非法输入抛 `CodecError`（`ValueError` 子类，定义在 `b85x/errors.py`）。
   - `encode_feed(data) -> str` / `decode_feed(text) -> bytes` 可调用任意次，
     `finish()` 返回残留输出；finish 之后继续 feed 的行为未约定。
   - **流式边界无关性**：同一输入按任意边界分块，各次 feed 的返回值拼接
     finish 的结果，与一次性处理整段输入的结果完全一致；解码同理。
2. **字符表**
   - Base85 字符表即 RFC 1924，按序为：

     0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_`{|}~

     共 85 个字符。无 `z` 特例，全零组也按普通 5 字符输出。
   - Base32 字符表即 RFC 4648（`A`-`Z` 加 `2`-`7`），位序为标准 5 位组大端拼接。
   - 解码端对字符表以外的任何字符（**包括空白字符**：空格、`\t`、`\r`、`\n`
     等）必须立即抛 `CodecError`，不得跳过或忽略。
3. **Base85 编码**
   - 每 4 字节按大端组成 32 位整数，转为 5 个 Base85 字符（高位在前）。
   - **padding 规则**：结尾不足 4 字节时，设尾长 n（1 <= n <= 3），先补
     `\x00` 到 4 字节按整组编码，取编码结果的前 **n+1** 个字符输出。
4. **Base85 解码**
   - 每 5 个字符还原 4 字节；组值超过 32 位抛 `CodecError`。
   - 结尾 1 个字符还原不出任何字节，抛 `CodecError`；结尾 m 个字符
     （2 <= m <= 4）用字符表最后一个字符 `~` 补足 5 位解码，取结果前 m-1 字节。
5. **Base32 编码**
   - 每 5 字节转 8 个字符；结尾尾长 n（1 <= n <= 4）时补 `\x00` 到 5 字节
     编码，取前 ceil(n*8/5) 个字符。本包不使用 `=` padding。
6. **Base32 解码**
   - 每 8 个字符还原 5 字节；结尾 m 个字符要求 m 属于 {2, 4, 5, 7}，解出
     floor(m*5/8) 字节；其余尾长抛 `CodecError`。

## 运行

```bash
python3 demo.py
```

## 测试报告

测试文件：`tests/test_codec.py`（标准库 unittest，可独立重复运行：
`python3 -m unittest tests.test_codec` 或 `python3 tests/test_codec.py`）。
共 23 个用例，16 绿 7 红，红用例上方注释均写明「README 期望 / 实际发生」。

红用例与对应缺陷：

1. `TestBase85Streaming.test_encode_chunk_boundary_independence`（红）——
   `Base85Encoder.encode_feed` 用 `self._carry += buf` 累加残余，而 buf 已
   包含旧 carry，分块喂入时旧残余被重复编码（分块收发大报文对不上的根因）。
   修复方向：改为 `self._carry = bytearray(buf)` 整体替换。
2. `TestBase85Encode.test_tail_padding_n3`（红）——`Base85Encoder.finish`
   截取长度写成 `(n + 1) % 4`，尾长 n=3 时输出空串，尾部 3 字节丢失。
   修复方向：截取长度改为 `n + 1`。
3. `TestBase85Streaming.test_roundtrip_various_lengths`（红）——上一条缺陷
   的连带表现：长度 ≡ 3 (mod 4) 的报文 roundtrip 后丢尾部 3 字节，
   随缺陷 2 一并修复。
4. `TestBase85Decode.test_whitespace_raises`（红）——`Base85Decoder.decode_feed`
   先过滤空白再校验，违反「任何字符表外字符（含空白）必须立即抛 CodecError」。
   修复方向：删除 `_WS` 过滤逻辑，直接逐字符校验。
5. `TestAlphabets.test_base32_alphabet_is_rfc4648`（红）——`base32.ALPHABET`
   为 `ABCDEFGHIJKLNMOPQRSTUVWXYZ234567`，'M' 与 'N' 位置互换。
   修复方向：改回 RFC 4648 标准字符表 `ABCDEFGHIJKLMNOPQRSTUVWXYZ234567`。
6. `TestBase32Encode.test_rfc4648_vectors`（红）——缺陷 5 在编码方向的表现
   （如 `b"foo"` 编成 `NZXW6` 而非 `MZXW6`），随缺陷 5 一并修复。
7. `TestBase32Decode.test_rfc4648_vectors`（红）——缺陷 5 在解码方向的表现，
   随缺陷 5 一并修复。

说明：Base32 自洽 roundtrip（`TestBase32Decode.test_roundtrip_various_lengths`）
为绿，因为字符表缺陷对编解码两端对称，只有与 RFC 4648 对端互通时才暴露；
`python3 demo.py` 所用的分块边界（8+8+2）恰好不触发缺陷 1、2，故 demo 照常通过。
