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

以下四类缺陷曾导致一次双主事故，均已修复；`tests/test_quorum_regression.py`
按当时的时序锁住了修复后的正确行为。

- **多数派门槛按旧成员数算死（法定人数漂移）**：老实现把
  `len(cluster) // 2 + 1` 在 `Quorum.__init__` 里算一次就缓存起来。
  备用节点扩容进 `MemberTable` 后，先起来的进程仍按老成员数凑票，
  5 个在册成员里只要 2 票就敢宣布当选，和按新成员数计票的一侧形成
  两个互不重叠的多数派。修复后 `majority()` 每次都按当前在册成员数
  动态计算，成员增减后门槛立刻变化。
- **活跃判定各用各的本机超时**：老实现的 `_active()` 用的是构造参数
  `timeout`（本机配置），而 `config["heartbeat_timeout"]`（集群协商值）
  只有 `negotiated_timeout()` 一个空壳出口，判定路径根本不经过它。
  于是本机超时配得宽松的节点，把另一侧早已判定超时的成员还算成活的，
  两边对"谁还活着"看法不一致，各自凑出自己的多数派。修复后 `_active()`
  统一走协商超时，没协商过时才退回本机配置，所有节点对存活的看法一致。
- **旧任期心跳被当成有效心跳**：老实现的 `heartbeat()` 完全不看
  `term`，上任 leader 醒过来补发的、带着过期任期号的心跳也会刷新
  `_seen` 时间戳，本该退位的节点由此被"算活"并继续参与计票。修复后
  `term` 落后于本节点当前任期的心跳一律拒绝、不刷新时间戳；`term`
  更新时先把本节点任期跟到新任期再采纳，任期号只许往前不许回退。
- **摘除成员的旧时间戳一直参与计票**：老实现的 `_seen` 只在收到心跳时
  写入，`MemberTable.remove()` 后旧时间戳仍留在表里，`_active()` 也只
  按时间过滤、不按在册关系过滤，导致人数虚高（摘除节点的票还在）。
  修复后 `_active()` 只统计当前在册成员，摘除立刻退出计票；摘除期间
  发来的心跳直接拒绝，节点重新加入后发出的心跳才会再次被采纳。
