# quorkit

配置中心选主用的法定人数小包。集群成员由外部注入的 `MemberTable` 描述，
所有时刻来自构造时传入的 clock；纯标准库，无外部依赖，测试不用等真实时间。

一个 `Quorum` 实例代表一个节点：记下自己收到的心跳、维护自己的任期号，
并按当前在册成员里的活跃多数派判断自己能不能当 leader。

## 模块说明

`quorkit/quorum.py`：

- `MemberTable(nodes=())`：在册成员表，提供 `add(node)` / `remove(node)` /
  `nodes()`（返回快照）/ `len(table)` / `node in table`。由外部持有，
  可以同时注入给多个节点，用来模拟各节点看到的成员视图。
- `Quorum(cluster, clock=time.monotonic, timeout=1.0, config=None)`：
  `cluster` 为注入的成员表，`timeout` 为本节点配置的失联超时，
  `config` 为集群商量好的公共配置（如 `{"heartbeat_timeout": 5.0}`）。
- `majority()`：凑够这么多票才算多数派。
- `heartbeat(node, ts, term=0)`：记下 node 在 ts 时刻的心跳，node 在这条
  心跳里声称自己处于 `term` 任期；返回这条心跳是否被采纳。
- `active()`：此刻还活着的节点集合，返回独立快照。
- `elect()`：按多数派把自己选成 leader，票够则任期加一并返回新任期，否则 None。
- `term()`：本节点目前的任期号，初始为 0。
- `negotiated_timeout()`：集群协商出来的失联超时；没协商过就退回本地配置。

`quorkit/__init__.py` 导出 `MemberTable`、`Quorum`。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## Known Issues
