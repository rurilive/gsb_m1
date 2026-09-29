# pushbuf

最朴素的无界先进先出缓冲，纯标准库，无外部依赖。

## 现状

pushbuf/buffer.py 提供 UnboundedBuffer：

- UnboundedBuffer()：建一个内存缓冲，内部就是一个列表
- put(item)：把元素追加到队尾并返回元素本身，永远成功
- get()：从队首取出一个元素，命中返回 (True, item)，空缓冲返回 (False, None)
- peek()：看一眼队首元素但不取出，空缓冲返回 (False, None)
- empty()：缓冲是否为空
- len()：当前元素个数
- clear()：清空缓冲

这层没有容量上限，put 永远不会失败，没有水位，也没有背压信号、拒绝与
丢弃策略，更没有唤醒顺序与计量。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_buffer.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10 及以上

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
