# gclab

内存堆上的垃圾回收实验室，纯标准库，无外部依赖。

## 现状

`gclab/heap.py` 提供 `RefCountHeap`：每次 `alloc` 得到一个对象编号，
对象表与引用表都是普通字典，`add_ref` 把被指对象的计数加一，`remove_ref`
减一，计数掉到零就当场回收，把该对象持有的引用逐条断开。根用 `add_root`
额外记一份外部引用，`roots`、`refs_of`、`ref_count`、`collected` 用来查询。
它没有标记阶段，没有清扫阶段，没有分代，也没有终结器与弱引用，环里的对象
互相引用，计数永远掉不到零，因此会泄漏。
`tests/test_heap.py` 锁住这些行为，一字不改。

## 目标（见任务描述）

把 `gclab` 从引用计数扩成标记清扫垃圾回收器，新增可达性标记、清扫与回收
计数、三色标记与写屏障、分新老两代的分代回收、终结器与弱引用，并补齐根为空、
环与自引用、混合对象图、非法输入 fail fast 等边界。全部仍在 `gclab` 包内，
纯标准库。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
