"""慢速参考最短路：朴素 Dijkstra。

只给测试和人工对拍用：实现直白、结果可复现，但图上没有启发式，图大时
要把目标附近的整片可达区域基本算完，当不了线上实现。
"""

import heapq

from gridnav.grid import GridError  # noqa: F401  (对外文档化的异常)


def dijkstra_path(grid, start, goal):
    """加权最短路，返回代价最小的路径（含起终点），不可达返回 None。

    起点或终点越界、被堵抛 GridError。代价并列时按 (x, y) 升序先出堆，
    同一地图上重复调用结果一致。浮点代价只做逐段累加，不额外舍入。
    """
    start = grid.require_cell(start, "start")
    goal = grid.require_cell(goal, "goal")
    if start == goal:
        return [start]
    dist = {start: 0.0}
    parent = {start: None}
    heap = [(0.0, start)]
    done = set()
    while heap:
        d, cur = heapq.heappop(heap)
        if cur in done:
            continue
        done.add(cur)
        if cur == goal:
            break
        for nx, ny, cost in grid.neighbors(cur[0], cur[1]):
            nxt = (nx, ny)
            if nxt in done:
                continue
            nd = d + cost
            if nd < dist.get(nxt, float("inf")):
                dist[nxt] = nd
                parent[nxt] = cur
                heapq.heappush(heap, (nd, nxt))
    if goal not in parent:
        return None
    path = []
    cur = goal
    while cur is not None:
        path.append(cur)
        cur = parent[cur]
    path.reverse()
    return path
