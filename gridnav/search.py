"""广度优先寻路：按层数扩展，只数步数，不看步长。"""

from collections import deque


def bfs_path(grid, start, goal):
    """八方向 BFS，返回步数最少的路径（含起终点），不可达返回 None。

    起点或终点越界、被堵抛 GridError。步数并列时按 neighbors 的枚举
    顺序先到先得，同一地图上重复调用结果一致。
    """
    start = grid.require_cell(start, "start")
    goal = grid.require_cell(goal, "goal")
    if start == goal:
        return [start]
    parents = {start: None}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        for nx, ny, _cost in grid.neighbors(cur[0], cur[1]):
            nxt = (nx, ny)
            if nxt in parents:
                continue
            parents[nxt] = cur
            if nxt == goal:
                queue.clear()
                break
            queue.append(nxt)
    if goal not in parents:
        return None
    path = []
    cur = goal
    while cur is not None:
        path.append(cur)
        cur = parents[cur]
    path.reverse()
    return path
