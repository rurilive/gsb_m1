# eventwire

边缘网关的进程内事件总线与记录文件，纯标准库，无外部依赖。

## 现状

`eventwire/topics.py` 管主题口径：

- `split_topic(topic)` 校验并切开主题：点号分段，段不能为空，
  主题里不许出现通配段
- `split_pattern(pattern)` 校验订阅模式：`*` 顶一段，`**` 只能放末尾
- `matches(pattern, topic)` 判模式是否覆盖主题，末尾的 `**` 可以一段都不顶

`eventwire/bus.py` 提供 `SyncBus`：

- `subscribe(name, handler, pattern="**")` 登记订阅，返回是否新名字；
  同名重复订阅替换处理器与模式、位置保持第一次订阅时的先后；
  处理器签名是 `handler(topic, payload)`
- `unsubscribe(name)` 删订阅，删掉返回 True，本来没有返回 False
- `subscriber_names()` 按订阅顺序给名字
- `publish(topic, payload)` 按订阅顺序同步调用所有匹配的处理器，
  返回调用次数；某个处理器抛异常，其余订阅者照样叫完，
  最后把第一个异常重新抛出

`eventwire/journal.py` 提供 `Journal(path)`：

- `append(record)` 把一条 dict 记录以一行 JSON 追加进文件并 flush
- `read()` 按写入顺序读回全部记录，空行跳过，末尾没写完的残行忽略，
  中间出现读不动的行报 `ValueError`
- `truncate()` 清空重来，`close()` 关句柄，也支持 `with` 写法

发布是全同步的：某一个订阅者慢，发布方和排在后面的订阅者都得等它。

## 目标

见任务描述。约束：

- `SyncBus` 与 `Journal` 的现有行为、`tests/` 下的基线保持不变（基线一个字不改）
- 纯标准库（json、threading 等在，装不了三方包），运行环境没有网络

## 运行

```bash
python3 demo.py                          # 主题匹配、落盘读回、同步分发演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
