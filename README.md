# wirepack

跟端上设备对接的二进制记录编解码库，纯标准库，无外部依赖。

## 线上格式

单条记录定长 16 字节，全部大端：

```
偏移  长度  字段
0     4     seq    无符号 32 位
4     1     kind   1=data, 2=ack, 3=ctrl
5     1     flags  保留位，原样透传
6     10    label  ASCII，右侧 NUL 补齐
```

`seq` 由上游位点分配器发放，约定不超过 800 万，编解码两端都按这个前提做校验：
写的时候超范围直接拒掉，读的时候超出范围按错位处理。

## 模块

- `wirepack/errors.py`：`WireError` 基类，`EncodeError` 与 `DecodeError`；
  解析异常带 `offset`（流内字节偏移）和 `field`（字段名）
- `wirepack/records.py`：`Record` 模型，`pack_record()` / `unpack_record()`，
  `MAX_SEQ`、`RECORD_SIZE`、`encode_label()` / `decode_label()`
- `wirepack/stream.py`：`RecordStream` 按块喂入（`feed()` 吃任意切分的字节块，
  `offset`、`pending` 反映消费与缓冲字节数，`finish()` 校验流末），
  另有 `iter_records()` 与切片工具 `chunked()`

流式解码只保留凑不满一条记录的尾巴，解析过的字节马上丢掉，内存不随流长增长。

## 运行

```bash
python3 demo.py                           # 布局、跨块喂入、吞吐、截断报错
python3 -m unittest discover -s tests -v  # 既有行为基线测试
```

## 约定

`tests/` 下的用例锁的是现有线上行为，改动前先跑一遍；
`RecordStream` 的行为（偏移口径、错位检测、流末校验）是对外的接口约定。
