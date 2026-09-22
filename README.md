# gridnav

栅格地图上的基础寻路库，纯标准库，无外部依赖。

## 现状

- `gridnav/grid.py` 提供 `Grid(width, height, blocked=())`：
  - 坐标 `(x, y)` 为整数，原点在左下角；`in_bounds` / `passable` 是全域查询，越界的 `is_blocked`、`neighbors`、`set_blocked` 抛 `GridError`
  - `set_blocked(x, y, flag=True)` 返回改动前的阻塞状态
  - 八方向移动：横竖一步代价 `1.0`，斜一步代价 `math.sqrt(2)`（模块常量 `SQRT2`）；两侧正交邻格都堵死时不允许斜穿，只堵一侧可以贴着滑过去
  - `neighbors(x, y)` 按固定的 `DIRECTIONS` 顺序返回 `(nx, ny, cost)`，`step_cost(a, b)` 单步折算
  - `blocked_cells()` 升序快照，`copy()` 独立副本，`require_cell(cell, name)` 做端点校验
- `gridnav/paths.py` 提供 `validate_path(grid, path)` 与 `path_cost(grid, path)`：
  路径是含起终点的 `(x, y)` 序列，非法路径抛 `PathError`；代价逐段累加，不做额外舍入
- `gridnav/search.py` 提供 `bfs_path(grid, start, goal)`：层序扩展、只数步数，
  不可达返回 `None`，端点被堵或越界抛 `GridError`，并列时按邻居枚举顺序先到先得
- `gridnav/reference.py` 提供 `dijkstra_path(grid, start, goal)`：朴素加权最短路，
  接口约定与 `bfs_path` 相同，结果可复现；没有启发式，图大时慢，只适合当对拍参考
- `gridnav/maps.py` 提供 `open_map`、`random_map(width, height, density, seed, protected)`、
  `pillared_map`；随机地图只由参数与种子决定，跨进程一致

## 目标

见任务描述。约束：

- 现有接口与 `tests/` 下的基线行为保持不变（基线一个字不改）
- 纯标准库，不引入三方依赖

## 运行

```bash
python3 demo.py                           # 现状演示
python3 -m unittest discover -s tests     # 行为基线测试
```
