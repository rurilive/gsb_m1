# sagakit

一个顺序步骤执行器，纯标准库，无外部依赖。现在只会把一串步骤按顺序跑完，
跑崩了就停在原地。

## 现状

sagakit/runner.py 提供 StepRunner：

- StepRunner(steps)：把步骤列表装进执行器，步骤是任意可调用对象
- run()：按列表顺序依次调用，把各步返回值收集成列表返回
- 任一步抛异常，整体立刻停止，异常向上抛出，后续步骤不再执行
- len(runner)：步骤数量

失败的时候已经跑过的步骤不会做任何回退，也不会重来。

## 目标

见任务描述。约束：

- 基线行为与 tests/test_runner.py 一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
