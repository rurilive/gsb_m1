# slabbin

进程内对象借还池，纯标准库，无外部依赖。

## 现状

slabbin/pool.py 提供最朴素的一进一出对象借还池 BorrowPool：

- Block(bid, payload=None)：池里的对象，带序号与可选负载
- BorrowPool(factory=None)：factory 可选自定义建造，缺省由池自己造 Block
- borrow()：借出对象，池里有空闲就复用，否则新建
- give_back(block)：把对象塞回空闲列表
- idle / created：空闲数量与累计新建数量

没有容量上限，没有空闲回收，没有尺寸分档，没有借出标记与生命周期管理。

## 目标（见任务描述）

约束：

- 现有行为与 tests/test_pool.py 基线一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
