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

以下四类问题已在当前版本修复，此处记录各自的现象与根因，供回溯对照。

### 1. 扩容后多数派门槛不跟着变（已修复）

现象：备用节点扩容进集群后，先启动的进程仍按老成员数凑票，
5 个成员里活 2 个就敢宣布当选。

根因：多数派门槛在 `Quorum.__init__` 里算好并存成 `_quorum_size`，
之后 `MemberTable` 的增删完全不会触发重算，门槛永远停在构造那一刻的
成员数上。修复后 `majority()` 每次按当前在册成员动态计算。

### 2. 各节点按本机超时判活，活跃视图对不上（已修复）

现象：两个节点本机 `timeout` 配置不同（如 30s 与 5s），对同一批心跳
得出不同的活跃集合，各自凑出各自的"多数派"，前后脚都当上 leader。

根因：`_active()` 用的是本节点构造时传入的 `self._timeout`，而集群
协商好的 `config["heartbeat_timeout"]`（`negotiated_timeout()`）只被
暴露、从未参与判定。修复后活跃判定一律走协商超时，本机配置仅在没有
协商值时兜底，各节点对"谁还活着"达成一致。

### 3. 旧任期的心跳仍被当成有效（已修复）

现象：上任 leader 醒过来补发的心跳带着过期的任期号，仍被采纳并刷新
活跃时间戳，把本该退位的节点又算活了。

根因：`heartbeat()` 完全不看心跳里声称的 `term`，无条件落盘。
修复后任期严格往前：携带任期低于本节点当前任期的心跳一律拒绝；
携带更高任期的心跳被采纳，同时本节点任期跟进到该值。

### 4. 被摘除的成员仍在计票（已修复）

现象：节点被运维从成员表摘掉后，它留在 `_seen` 里的旧时间戳仍参与
活跃判定和计票，活跃人数虚高。

根因：`_active()` 只按时间戳过滤，从不核对节点是否还在册。
修复后活跃判定先以当前在册成员为界，不在册的节点（包括从未加入过的
陌生节点）一律不计票。
