# actorbox

对一对名字与处理器做同步分发的小模块，纯标准库，无外部依赖。

## 现状

actorbox/registry.py 提供一个 Registry：

- register(name, handler)：把一个可调用对象挂在名字下，重复注册拒绝
- unregister(name)：摘掉一个名字，不存在拒绝
- has(name) / names()：查看当前注册的名字
- send(name, message)：在调用方线程里直接调用处理器，返回值原样带回

没有邮箱，没有排队，send 调用返回就代表处理器已经跑完；处理器抛出的
异常被包装成 HandlerError 向上抛，原始异常挂在 __cause__ 上。

## 问题

同步直调把调用方和处理器死死绑在一起：处理器耗时就把调用方一起卡住，
一批消息没法先投递再处理；没有邮箱就更谈不上投递顺序与背压；一个
处理器崩掉整条调用链就断，没有重启与导出；也没有生命周期，停不下来，
停下的消息去了哪里说不清；这些缺口让它撑不起一个真正的 actor 运行时。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_sync.py 基线一致（基线一个字不改）
- 新行为另开 tests/test_actor.py
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
