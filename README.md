# chunkheap

进程内大块分配器，纯标准库，无外部依赖。

## 现状

chunkheap/alloc.py 提供最朴素的一进一出大块分配器 BumpAlloc：

- HeapError：异常基类，AllocError 从其派生
- BumpAlloc(capacity)：给定总容量，内部分配游标从零开始
- HEADER：每块块首的头部字节数，记录大小与占用标记
- alloc(size)：从末尾切出头部加请求字节数，返回头部之后的数据偏移
- free(offset)：空操作，只标记不再占用，不回收也不复用
- capacity / used：总容量与已切出字节数
- message()：一句人类可读的现状说明

没有空闲表，没有复用，没有相邻合并，没有对齐管理，也没有碎片统计，
容量只减不增。

## 目标（见任务描述）

约束：

- 现有行为与 tests/test_alloc.py 基线一致（基线一个字不改）
- 纯标准库，所有自定义异常继承 HeapError 基类
- 新行为另开测试文件，不与被锁定的基线文件重名

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
