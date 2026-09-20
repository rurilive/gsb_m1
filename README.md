# handshake

长连接会话的握手状态机：转移表驱动，时钟注入，事件进出全量日志。
单进程内嵌，纯标准库，无外部依赖。

## 模块结构

    handshake/
    ├── states.py    State / Ev / 定时器常量 T_* / 套件常量
    ├── table.py     Row / TABLE / 守卫与动作函数
    └── session.py   Session / LogEntry / ProtocolError

## 状态与事件

握手路径：CLOSED -> HELLO_SENT -> KEY_SENT -> AUTH_SENT，认证通过后按
套件分流进稳态：strong -> FULL，weak -> DEGRADED。对端报未知套件、
认证失败或任一阶段超时都回 CLOSED。

事件（`Ev`）：`START`（我方发起）、`PEER_HELLO`（payload 为套件名）、
`PEER_KEY`、`PEER_AUTH_OK`、`PEER_AUTH_FAIL`、`PEER_CLOSE`，以及由
`poll()` 合成的 `TIMEOUT`。

## 转移表语义

行为全部来自 `table.TABLE`，`feed`/`poll` 本身不含状态分支：

- 表按 (当前状态, 事件) 组织，同一组合可以多行，按书写顺序取第一条
  全部守卫通过的行；没有任何行生效抛 `ProtocolError`（消息含状态与事件）
- `guards`：守卫 `(payload, session) -> bool`，判定不许有副作用
- `actions`：动作 `(session, payload)`，状态变更后按序执行
- `sends`：发出的对端消息名，进 `outbox`（(ts, 消息名) 列表）并写日志
- `timer`：进入目标状态后武装的定时器秒数；`None` 表示无定时器

## 定时器与 poll

进入带 `timer` 的状态时记 deadline = clock() + timer。`poll()` 在
clock() >= deadline 时合成 `TIMEOUT` 事件走同一张表（先记 timeout
日志再迁移）；到点之前 `poll()` 是空操作，无定时器的状态下也是空操作。

## 日志

`Session.log` 是 `LogEntry(ts, kind, detail)` 列表，按发生顺序追加，
时间戳全部来自注入时钟。kind：`recv`（外部事件）/ `timeout` /
`move`（状态迁移，detail 为 `A->B`）/ `send`（对端消息）。

## 运行

    python3 demo.py                          # 握手/降级/超时三段演示
    python3 -m unittest discover -s tests -v # 行为基线测试
