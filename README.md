# snapwatch

轮询式目录监听，纯标准库，无外部依赖。隔一段时间扫一遍目录树，跟前一次快照
比对，把差异变成事件交给调用方。适合挂载盘、网络盘这类不支持 inotify 的地方。

## 用法

```python
from snapwatch import Watcher

watcher = Watcher("/data/builds")
watcher.subscribe(lambda event: print(event))
watcher.start()          # 后台线程按 interval 反复扫描
...
watcher.stop()
```

也可以自己控制节奏，按批次拿事件：

```python
events = watcher.poll()  # 扫一遍，返回这批事件，同时喂给回调
```

- `Watcher(root, fs=None, clock=time.time, interval=0.5)`：`fs` 是文件系统
  访问的替身（默认 `SysFS`），`clock` 是时钟，默认挂钟，和文件 mtime 在同一根
  时间轴上；测试里可以换成 `snapwatch.ManualClock`
- `poll()`：扫一遍并返回事件列表，回调按同一顺序逐个收到同一批事件对象
- `subscribe(callback)`：挂回调
- `start()` / `stop()`：后台线程模式，stop 可以重复调
- `snapshot()`：最近一次扫描的 `Snapshot`；`last_poll_at`：最近一次
  poll 的时钟读数
- 构造时先扫一次，用来打底，之后 `poll()` 只报真正的变化

事件类型四种：`created`、`modified`、`deleted`、`moved`。`moved` 的 `path`
是旧路径，`dest` 是新路径。事件对象有 `kind`、`path`、`dest`、`is_dir`。

`snapwatch/scanner.py` 里的 `PollScanner(fs, root).scan()` 单独也能用，返回
`Snapshot`，用相对 root 的 posix 路径做键，`entry(path)` 拿 `Entry`
（`is_dir`、`size`、`mtime_ns`、`inode`、`digest`，digest 是内容的 sha256）。

## 对拍工具

`snapwatch/reference.py` 里有一套对拍用的东西：

- `OpScript(root, clock, granularity=1.0, seed=1)`：在真实目录上做随机文件
  操作（建、写、追加、删、改名、原子替换、改时间戳、建目录），每一步之后把
  可观测状态记进操作日志。它按 `granularity` 秒的时间片给文件打 mtime，
  这样时间戳精度不靠真机
- `OpReference(debounce=0.25)`：只看操作日志，`prime(存量状态)` 打底，
  之后每轮 `feed(now, ops)` 返回这一轮 `poll()` 该给出的事件列表
- `state_of(path)`：路径当前的可观测状态；`publish`、`sort_key`：把净变化
  收成一批排好序的事件，OpReference 内部用它们出基准

## 运行

```bash
python3 demo.py                          # 现状演示，四类现场
python3 -m unittest discover -s tests -v # 行为基线测试
```
