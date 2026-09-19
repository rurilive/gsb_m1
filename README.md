# utf8stream

接入网关自研的增量 UTF-8 解码器，按块喂字节、流式吐文本，纯标准库，无外部依赖。

## 模块说明

`utf8stream/decoder.py` 提供解码器 `Utf8Decoder(errors="strict" | "replace")`：

- `feed(chunk)`：喂一块字节，返回本次解出的文本；解码结果与分块方式无关
- `flush()`：流结束时收尾，残序列按 errors 策略处理
- `consumed`：累计真正处理过的字节数（解码掉的 + 按错误策略吃掉的），上游按它推进源读指针
- 流首的 UTF-8 BOM（EF BB BF）只剥离一次，不会出现在解码结果里
- `errors="strict"`：非法字节抛 `Utf8DecodeError`；`"replace"`：仅坏字节本身被 U+FFFD 顶替，其后的字节照常解码

## 运行

```bash
python3 demo.py
```

## Known Issues
