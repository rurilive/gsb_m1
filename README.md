# buskit

纯标准库的内存消息代理，无外部依赖。

## 现状

buskit/broker.py 提供最简单的发布订阅 MessageBus：

- subscribe(topic, callback)：订阅主题，回调收一个 Message
- unsubscribe(sub)：取消订阅，已取消的返回 False
- publish(topic, payload)：给该主题全部活跃订阅者投递一条消息，返回消息序号
- 订阅回调抛出的异常被吞掉并记入 errors，不影响其它订阅者
- Message 带 topic、payload 与 per-topic 自增的 seq

## 问题

投递是即发即忘：回调一返回就算送达，回调失败或消费者中途挂掉这条消息就丢了；
也没有消费者过滤、没有队列上限的概念，更没有按序号回放的能力。生产端一股脑
publish，慢消费者只能眼睁睁看着内存涨。

## 目标

在当前基础上补出确认与重投、订阅过滤、背压与回放，见任务描述。约束：

- 现有行为与 tests/test_broker.py 基线保持一致（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
