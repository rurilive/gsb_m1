# pather

纯标准库的点号路径取值器，无外部依赖。

## 现状

pather/getter.py 只提供最朴素的取值能力：

- Getter(root)：拿着一个嵌套字典作为根
- get(path)：把点号分隔的路径按点切段，从根开始逐层取字典键
- 任意一层取不到、或中途遇到的对象不是字典，就返回 None
- 空路径返回根本身，非字符串路径抛 TypeError
- 没有数组下标、通配、过滤、递归下降，也没有切片

tests/test_getter.py 把上述基线行为锁住，一字不改。

## 目标（见任务描述）

在现有 Getter 之上把 pather 扩成一个 JSON 路径查询引擎：路径表达式编译成步骤
序列，能对嵌套的字典与列表混合结构求值，支持数组下标、通配字段与通配下标、
递归下降、切片，能在数组上按比较过滤，能对匹配位置做替换与删除，非法路径与
越界查询 fail fast。全部仍在 pather 包内，纯标准库。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
