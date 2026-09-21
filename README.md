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

- `Watcher(root, fs=None, clock=time.time, interval=0.5, debounce=0.25,
  granularity=1.0)`：`fs` 是文件系统访问的替身（默认 `SysFS`），`clock` 是
  时钟，默认挂钟，和文件 mtime 在同一根时间轴上；测试里可以换成
  `snapwatch.ManualClock`。`debounce` 是静默秒数，变化静默这么久才发布，
  静默期里又变则重新计时；`granularity` 是盘上 mtime 的时间片宽度（秒），
  含义见文末「时间戳精度」
- `poll()`：扫一遍并返回事件列表，回调按同一顺序逐个收到同一批事件对象。
  对同一路径只报相对上次已发布状态的净效果：一轮里出现又消失不报，原子
  改名（写临时文件再 `os.replace`）报 `modified` 而不是 deleted+created；
  同一 inode 旧路径消失、新路径出现时配成 `moved`，新路径原本已存在则按
  `modified`。批内顺序为 deleted（深的在前）、modified、moved、created
  （浅的在前）
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


## 时间戳精度

轮询只能看到 `(mtime, size, inode)` 三类元数据，不支持 inotify 的盘上这是
全部线索。两处精度问题单独处理：

- **静默合并（`debounce`，默认 0.25 秒）**：编辑器一次保存里连写几笔，
  每笔都去重报事件没有意义。一个路径的变化要先静默 `debounce` 秒才发布，
  静默期里又有变化就从最后一次扫描重新计时；发布时比对的是上一次已发布
  状态，所以连写多少笔都只出一条净效果事件，一轮里出现又消失（临时文件
  当轮就被改名盖掉）完全不报。
- **粗 mtime 时间片（`granularity`，默认 1.0 秒）**：有些挂载盘的 mtime
  只到秒（甚至更粗）。同一时间片里连改两笔、文件长度又一样时，元数据
  完全相同，不读内容无法分辨。Watcher 只对这类可能藏变化的文件惰性读一次
  内容算 sha256：
  - 扫描本身永远只读元数据，不碰文件内容。
  - 只有「元数据和上轮一模一样、且 mtime 还在最近一个 `granularity`
    秒窗口内」的文件才需要读内容；已经熬过一个完整时间片的文件，之后的
    写入按时间片取整必然拿到新 mtime，内容确认一次后按
    `(inode, mtime)` 缓存，静止的树一轮零读盘。
  - 一个 inode 第一次被看到时的那个 mtime 永远不进缓存——它可能正被
    同时间片的连写复用；要等它后来拿到更新的 mtime 才信任缓存。
  - 盘的实际粒度比 1 秒粗（例如某些 FAT/网络盘按 2 秒取整）时，把
    `granularity` 设成对应秒数。
- **目录读不出来（权限瞬断、chmod、挂载抖动）**：扫描会把列不出内容的
  目录记进 `Snapshot.incomplete`，Watcher 沿用上一轮这棵子树的条目，
  不把它们误报成删除；下次能读了再正常比对。

代价是：在变化刚发生的一个 `granularity` 窗口内，被改动的文件会各读
一次内容；窗口之外、以及静止的目录树，扫描没有任何文件内容读取。
