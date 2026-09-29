# swimsim

一个纯标准库的去中心化成员关系协议，无外部依赖。集群里的节点要彼此知道
谁还在、谁没了，还要在没人下命令的前提下把这个事实传到每一个角落，swimsim
就是干这件事的那一层。

## 现状

- `swimsim/clock.py`：`ManualClock(start, step)`，可注入、可手动推进的逻辑
  时钟，协议只认它的 `now`，不读系统墙上时间。
  - `advance(n)`：把时钟向前推 n 步
- `swimsim/member.py`：`MemberRecord(name, alive, last_seen)`，成员的一条
  状态记录。
  - `seen_at(moment)`：刷 `last_seen` 后的新记录
  - `snapshot()`：可序列化快照
- `swimsim/node.py`：`Node(name, members, clock)`，一张静态成员表加整表广播。
  - `add_member` / `has` / `known`：加成员、查成员、列全部成员
  - `record` / `is_alive`：取某成员的记录、查它是否存活
  - `observe(member, alive)`：按一次外部观察更新记录
  - `gossip(member)`：把整张成员表打成快照
  - `merge(snapshot)`：按 `last_seen` 大小合并对端快照
- `swimsim/errors.py`：`SwimError` 基类与 `DefinitionError` / `UnknownMember`
  / `IllegalTransition` / `SelfProbeRejected` / `NotHeartbeatTime` 五种具体
  错误。

## 问题

成员表是静态的：它不会自己随时间变化，没人去探测谁到底还在不在；存活只有
是或否两种，没有怀疑这种中间态，一个刚掉线的节点要么被当成活的要么被当成
死的；状态记录里没有版本号，两个节点各自看到的同一成员谁新谁旧只能比时间，
改一次状态就可能把别人更新的判断覆盖掉；节点之间只有一次性广播，没有反熵，
一次没传到的状态就一直传不到，全网收敛没有保证；死掉的节点也没有一条重新
加入并被重新接受的路子。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```