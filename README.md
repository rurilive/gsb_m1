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

运行方式（纯标准库，仓库根目录下任选其一）：

```bash
python3 tests/test_codec.py
python3 -m unittest tests.test_codec -v
python3 -m unittest discover
```

共 31 个用例：25 绿，6 个红用例（`@unittest.expectedFailure`，注释中标注
「README 期望 / 实际发生」）。红用例对应源码与 README 的 4 处出入：

1. **Base32 字符表 M/N 写反**（红：`AlphabetTests.test_b32_alphabet_is_rfc4648`、
   `B32KnownAnswerTests.test_encode_rfc4648_vectors`、
   `B32KnownAnswerTests.test_decode_rfc4648_vectors`）：`b85x/base32.py` 的
   `ALPHABET` 为 `"...JKLNMOP..."`，与 README 第 2 节的 RFC 4648 字符表
   `"...JKLMNOP..."` 不符，编码/解码两端产出同时偏离标准且可自洽 roundtrip，
   对账时表现为双方若版本不一致即内容对不上；修复方向：把常量改回
   `"ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"`。
2. **Base85 尾长 n=3 丢尾**（红：`B85KnownAnswerTests.test_encode_tail_n3`）：
   `b85x/base85.py` 的 `finish` 用 `(n + 1) % 4` 切片，n=3 时截取 0 个字符，
   与 README 第 3 节「取前 n+1 个字符」不符，3 字节尾报文静默丢尾；修复方向：
   切片改为 `[: n + 1]`。
3. **Base85 编码流式残留重复拼接**（红：
   `StreamBoundaryTests.test_b85_encode_chunk_independent`）：
   `encode_feed` 中 `self._carry += buf` 把上一轮残留又拼了一次，非 4 倍数
   分块边界下输出重复/错组，违反 README 第 1 节流式边界无关性，正是改成分块
   收发后偶发对账不符的直接原因；修复方向：合并后整体重切，即
   `self._carry = bytearray(buf)`。
4. **Base85 解码静默吞掉空白**（红：
   `B85KnownAnswerTests.test_decode_whitespace_must_raise_immediately`）：
   `decode_feed` 先过滤空白字符再解码，与 README 第 2 节「字符表以外的任何
   字符（包括空白）必须立即抛 `CodecError`」不符，带空白的坏报文被悄悄改写；
   修复方向：删除空白过滤分支，由非法字符检查直接抛错。

`python3 demo.py` 未受影响，照常跑通；`b85x/` 源码与 `demo.py` 在本次工作中
未做任何改动。
