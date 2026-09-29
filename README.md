# taskq

带优先级与延迟的任务调度器，纯标准库，无外部依赖。

## 现状

taskq/queue.py 提供 FifoQueue：

- push(task)：把任务放到队尾，返回任务本身；任务为 None 抛 ValueError
- pop()：从队首取出一个任务，队列为空返回 None
- peek()：看一眼队首任务但不取走，队列为空返回 None
- len() / bool()：队列长度与是否非空

任务体不做任何校验或变换，入队是什么、出队还是什么，没有优先级、没有延迟、
没有租约，也没有重试。tests/test_queue.py 锁住这些行为。

## 问题

队列只有先进先出，紧急任务没法插到前面；想让任务过一会儿再处理只能自己在外层
算好时间再入队；任务被取走后不管消费者成没成功都不会再出现，消费者中途失败
任务就丢了；没有任何凭据保证同一任务不被两个消费者同时拿走。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_queue.py 基线一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
