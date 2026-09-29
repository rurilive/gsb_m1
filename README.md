# packlex

字节编解码小库，纯标准库，无外部依赖。调用方喂进一段字节，希望输出比
输入更短，同时保证再解码能逐字节拿回原始数据。

## 现状

- `packlex/codec.py`：`IdentityCodec`，一套恒等编码。`encode(data)` 把
  输入字节原样返回，`decode(data)` 把输入字节原样返回，两者都要求 bytes
  或 bytearray，否则抛 TypeError。对任意字节串，encode 再 decode 能逐字节
  还原。

现状是最朴素的实现：输出长度永远等于输入长度，没有压缩；没有字典，没有
回溯引用，没有变长整数，也没有滑动窗口与分块的概念。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
