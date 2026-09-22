"""增量 A* 寻路：AStarPlanner。

plan(start, goal) 用可采纳的对角线启发式（octile）做正向 A*，开放列表
是堆；replan(start, goal) 在 set_blocked 改动后复用上一轮的 g/rhs 搜索
状态做 LPA* 式增量修复，只把受影响的格子重新入堆，不整条重搜；没堵到
当前最短路时一次展开都不会发生。

启发式：h = (mx - mn) * 1.0 + mn * SQRT2（mn/mx 为到终点横纵位移的
小者/大者），再乘 (1 - 1e-9) 的收缩系数。收缩系数保证浮点舍入不会把
h 抬过真实剩余代价，可采纳性不被浮点误差破坏；1e-9 远小于任意两条
不同路径的代价差（横竖 1.0、斜 SQRT2 的组合之间至少差 1e-4 量级），
不影响最优性。

堆键为 (f, -min(g, rhs), 格子 id)：f 并列时优先更深的节点以减少展开
数，id 兜底给出确定的全序，同一地图重复调用、跨进程调用结果一致。
"""

import heapq
import math

SQRT2 = math.sqrt(2.0)

_H_SCALE = 1.0 - 1e-9
_INF = float("inf")

# 与 gridnav.grid.DIRECTIONS 同序：东、东北、北、西北、西、西南、南、东南。
_DIRS = ((1, 0), (1, 1), (0, 1), (-1, 1),
         (-1, 0), (-1, -1), (0, -1), (1, -1))


class AStarPlanner:
    """绑定一张 Grid 的增量 A* 规划器。"""

    def __init__(self, grid):
        self.grid = grid
        self.name = None
        self._w = grid.width
        self._h = grid.height
        self._moves = tuple(
            (dx, dy, dy * self._w + dx, SQRT2 if dx and dy else 1.0)
            for dx, dy in _DIRS
        )
        self._blocked = bytearray(self._w * self._h)
        self._blocked_cells = set()
        for x, y in grid.blocked_cells():
            self._blocked[y * self._w + x] = 1
            self._blocked_cells.add((x, y))
        self._g = None
        self._rhs = None
        self._open = None
        self._heap = None
        self._sid = None
        self._query = None
        self._path = None
        self._expansions = 0
        self._last_expansions = 0
        self._plans = 0
        self._replans = 0

    # -- 启发式 ------------------------------------------------

    @staticmethod
    def heuristic(a, b):
        """(x, y) 到 (x, y) 的对角线启发式，含抗舍入收缩，恒不大于真实代价。"""
        dx = abs(a[0] - b[0])
        dy = abs(a[1] - b[1])
        mn = dx if dx < dy else dy
        mx = dx if dx > dy else dy
        return ((mx - mn) + mn * SQRT2) * _H_SCALE

    # -- 对外查询 ----------------------------------------------

    def plan(self, start, goal):
        """全量 A*：返回代价最小的路径（含起终点），不可达返回 None。

        起点或终点越界、被堵抛 GridError。代价并列时按固定规则选路，
        同一地图上重复调用、跨进程调用结果一致。
        """
        start = self.grid.require_cell(start, "start")
        goal = self.grid.require_cell(goal, "goal")
        self._plans += 1
        self._search_fresh(start, goal)
        return list(self._path) if self._path is not None else None

    def replan(self, start, goal):
        """增量重规划：端点与上次相同且地图只改了阻塞格时只修复受影响段。

        没堵到当前路径时不展开任何节点；端点变了或还没规划过时退化为
        一次全量搜索。返回值与异常约定同 plan。
        """
        start = self.grid.require_cell(start, "start")
        goal = self.grid.require_cell(goal, "goal")
        self._replans += 1
        if self._query != (start, goal) or self._g is None:
            self._search_fresh(start, goal)
        else:
            self._repair(start, goal)
        return list(self._path) if self._path is not None else None

    def stats(self):
        """累计统计：expansions 为历次 plan/replan 的节点展开总数。"""
        return {
            "expansions": self._expansions,
            "last_expansions": self._last_expansions,
            "plans": self._plans,
            "replans": self._replans,
        }

    # -- 阻塞同步 ----------------------------------------------

    def _sync_blocked(self):
        """把 grid 的阻塞变化同步进内部结构，返回 (新堵 id 列表, 新通 id 列表)。"""
        live = self.grid._blocked
        mine = self._blocked_cells
        newly_blocked = live - mine
        newly_opened = mine - live
        if not newly_blocked and not newly_opened:
            return [], []
        w = self._w
        blocked = self._blocked
        blocked_ids = []
        for cell in newly_blocked:
            x, y = cell
            cid = y * w + x
            blocked[cid] = 1
            mine.add(cell)
            blocked_ids.append(cid)
        opened_ids = []
        for cell in newly_opened:
            x, y = cell
            cid = y * w + x
            blocked[cid] = 0
            mine.discard(cell)
            opened_ids.append(cid)
        return blocked_ids, opened_ids

    # -- 搜索 --------------------------------------------------

    def _search_fresh(self, start, goal):
        self._sync_blocked()
        self._query = (start, goal)
        self._g = None
        self._rhs = None
        self._open = None
        self._heap = None
        if start == goal:
            self._path = [start]
            self._last_expansions = 0
            return
        n = self._w * self._h
        self._g = [_INF] * n
        self._rhs = [_INF] * n
        self._open = {}
        self._heap = []
        sid = start[1] * self._w + start[0]
        gid = goal[1] * self._w + goal[0]
        self._sid = sid
        self._rhs[sid] = 0.0
        key0 = self.heuristic(start, goal)
        self._open[sid] = (key0, 0.0)
        heapq.heappush(self._heap, (key0, 0.0, sid))
        expansions = self._run(gid, goal)
        self._expansions += expansions
        self._last_expansions = expansions
        self._path = self._extract(sid, gid, start)

    def _repair(self, start, goal):
        newly_blocked, newly_opened = self._sync_blocked()
        if not newly_blocked and not newly_opened:
            self._last_expansions = 0
            return
        w = self._w
        hgt = self._h
        gid = goal[1] * w + goal[0]
        for cid in newly_blocked + newly_opened:
            y, x = divmod(cid, w)
            self._update_vertex(cid, x, y, goal)
            for dx, dy, did, _cost in self._moves:
                nx = x + dx
                ny = y + dy
                if 0 <= nx < w and 0 <= ny < hgt:
                    self._update_vertex(cid + did, nx, ny, goal)
        expansions = self._run(gid, goal)
        self._expansions += expansions
        self._last_expansions = expansions
        self._path = self._extract(self._sid, gid, start)

    def _run(self, gid, goal):
        """LPA* 主循环：弹出堆顶最小键的格子并处理，返回本次展开数。"""
        g = self._g
        rhs = self._rhs
        blocked = self._blocked
        moves = self._moves
        w = self._w
        hgt = self._h
        open_d = self._open
        heap = self._heap
        gx, gy = goal
        heappush = heapq.heappush
        heappop = heapq.heappop
        expansions = 0
        while True:
            top = None
            while heap:
                cand = heap[0]
                if open_d.get(cand[2]) == (cand[0], cand[1]):
                    top = cand
                    break
                heappop(heap)
            if top is None:
                break
            gm = g[gid]
            rv = rhs[gid]
            mgoal = gm if gm < rv else rv
            if gm == rv and (top[0], top[1]) >= (mgoal, -mgoal):
                break
            heappop(heap)
            uid = top[2]
            del open_d[uid]
            expansions += 1
            y, x = divmod(uid, w)
            gu = g[uid]
            ru = rhs[uid]
            if gu > ru:
                g[uid] = ru
                for dx, dy, did, cost in moves:
                    nx = x + dx
                    ny = y + dy
                    if 0 <= nx < w and 0 <= ny < hgt:
                        if dx and dy and blocked[uid + dx] \
                                and blocked[uid + dy * w]:
                            continue
                        nid = uid + did
                        if blocked[nid]:
                            continue
                        ng = ru + cost
                        if ng < rhs[nid]:
                            rhs[nid] = ng
                            gn = g[nid]
                            m = gn if gn < ng else ng
                            hx = nx - gx
                            if hx < 0:
                                hx = -hx
                            hy = ny - gy
                            if hy < 0:
                                hy = -hy
                            mn = hx if hx < hy else hy
                            mx = hx if hx > hy else hy
                            key0 = m + ((mx - mn) + mn * SQRT2) * _H_SCALE
                            key1 = -m
                            open_d[nid] = (key0, key1)
                            heappush(heap, (key0, key1, nid))
            else:
                g[uid] = _INF
                self._update_vertex(uid, x, y, goal)
                for dx, dy, did, _cost in moves:
                    nx = x + dx
                    ny = y + dy
                    if 0 <= nx < w and 0 <= ny < hgt:
                        self._update_vertex(uid + did, nx, ny, goal)
        return expansions

    def _update_vertex(self, uid, x, y, goal):
        """按当前 g 值全量重算 rhs(uid)，并维护它在开放列表里的位置。"""
        g = self._g
        rhs = self._rhs
        if uid == self._sid:
            new = 0.0
        elif self._blocked[uid]:
            new = _INF
        else:
            new = _INF
            w = self._w
            hgt = self._h
            blocked = self._blocked
            for dx, dy, did, cost in self._moves:
                nx = x + dx
                ny = y + dy
                if 0 <= nx < w and 0 <= ny < hgt:
                    if dx and dy and blocked[uid + dx] \
                            and blocked[uid + dy * w]:
                        continue
                    pid = uid + did
                    if blocked[pid]:
                        continue
                    cand = g[pid] + cost
                    if cand < new:
                        new = cand
        rhs[uid] = new
        gm = g[uid]
        if new == gm:
            self._open.pop(uid, None)
            return
        m = gm if gm < new else new
        gx, gy = goal
        hx = x - gx
        if hx < 0:
            hx = -hx
        hy = y - gy
        if hy < 0:
            hy = -hy
        mn = hx if hx < hy else hy
        mx = hx if hx > hy else hy
        key0 = m + ((mx - mn) + mn * SQRT2) * _H_SCALE
        key1 = -m
        self._open[uid] = (key0, key1)
        heapq.heappush(self._heap, (key0, key1, uid))

    # -- 路径提取 ----------------------------------------------

    def _extract(self, sid, gid, start):
        """从终点沿最优前驱走回起点；rhs 不可达（inf）时返回 None。"""
        g = self._g
        if g[gid] == _INF:
            return None
        blocked = self._blocked
        w = self._w
        hgt = self._h
        path = []
        uid = gid
        while uid != sid:
            y, x = divmod(uid, w)
            path.append((x, y))
            best = _INF
            best_id = -1
            for dx, dy, did, cost in self._moves:
                nx = x + dx
                ny = y + dy
                if 0 <= nx < w and 0 <= ny < hgt:
                    if dx and dy and blocked[uid + dx] \
                            and blocked[uid + dy * w]:
                        continue
                    pid = uid + did
                    if blocked[pid]:
                        continue
                    cand = g[pid] + cost
                    if cand < best:
                        best = cand
                        best_id = pid
            if best_id < 0:
                return None
            uid = best_id
        path.append(start)
        path.reverse()
        return path
