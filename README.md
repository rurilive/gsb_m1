# xlock

基于锁文件的跨进程互斥，给本机的批处理任务保护共享资源用，纯标准库。

## 用法

```python
from xlock import LockTimeout, ResourceGuard

guard = ResourceGuard("/var/tmp/batch-locks")
try:
    with guard.hold("index", timeout=5):
        rebuild_index()
except LockTimeout:
    print("索引维护任务正忙，稍后再来")
```

- `ResourceGuard(lock_dir, timeout=None, poll=0.05, steal_after=None, proc=None, fs=None)`
  - `hold(name, timeout=None)` 拿资源，返回 `Lease`；被占且超时抛 `LockTimeout`
  - `path(name)` 资源的锁文件路径，`is_held(name)`、`owner(name)` 查询状态
  - `events()` 本 guard 的进出流水，元素是 `(序号, 事件, 资源, pid, 时间)`
  - 同一个 guard 里对同一资源可以嵌套 hold，最外层退出时才真正释放
- `FileLock(path, timeout=None, poll=0.05, steal_after=None, proc=None, fs=None)`
  - `acquire(timeout=None)` 拿锁，拿到 True、超时 False；`release()` 释放
  - `is_mine()` 锁文件里记的是不是本进程；`is_held()` 有没有人拿着
  - `owner()` 读持有者信息（`LockInfo`，有 `pid` 和 `at` 两个字段）
  - 锁文件记录持有者 pid 和拿锁时间，创建锁文件即持有，删掉即释放
  - 同一路径上的锁不重入，同一个进程里开两把 `FileLock` 也要互相等
- 可注入的环境：`ProcEnv`（pid、存活判断、身份指纹、墙钟 / 单调钟、
  sleep）和 `FileOps`（锁文件的建、读、改写、删、取修改时间）。测试用
  假对象替换它们，构造自己想要的时序
- `xlock.arbiter` 里是集中式仲裁的参考实现（单仲裁者服务端加
  Unix socket 客户端），接口语义和 `FileLock` 对齐，连断即释放。
  它只用来做对照测试，线上路径不依赖它
- `steal_after` 是锁文件的存在时长门槛，超过这么多秒才允许接管，
  默认 `None`（不接管）

## 运行

```bash
python3 demo.py                           # 现状演示
python3 -m unittest discover -s tests -v  # 行为基线测试
```
