# logstore

一个内存 KV 存储，纯标准库，无外部依赖。

## 现状

logstore/store.py 提供 KVStore：

- put(key, value)：写入或覆盖，返回是否覆盖了已有的键
- get(key, default=None)：取当前值，键不存在返回 default
- delete(key)：删除键，返回该键此前是否存在
- keys()：当前存在的键，按升序
- items()：当前存在的键值对，按键升序
- __len__ / __contains__：键数与成员判断

所有键值都存在一个字典里，没有分段、没有版本、没有合并。

## 问题

所有数据挤在一层，写入直接覆盖旧值，看不到历史；删除直接抹键，
删掉的键无从遮蔽更旧的数据；没有范围扫描，只能按键逐个取；
也没有合并与回收的口径，副本只增不减。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_dict.py 基线一致（基线一个字不改）
- 新行为另开测试文件
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
