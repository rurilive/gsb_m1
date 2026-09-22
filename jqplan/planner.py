"""连接顺序规划。

Planner.plan 拿统计快照估中间结果大小，按"探测行数"的口径给顺序打分：
第 k 张表的代价是前 k-1 张表的估计中间结果行数乘上这张表的行数。
一组表的估计行数是各表行数的积，再乘上组内每条等值条件的选择率
（1 / max(两侧列基数)）。

选顺序用子集动态规划，2^n 个状态，十一张表也出得来，不用穷举排列。
条件图里互不相连的表由 Planner.components 分组，组内各自排好，
组之间再按叉积代价排一遍。统计缺失、过期或者对不上查询时，
整体退回声明顺序。同样的查询加同样的统计，每次给出同一个计划。
"""

from .engine import Plan


class Planner:
    """给出查询的执行计划。"""

    def plan(self, query, stats=None):
        """按估计代价出计划。没有统计或统计对不上表时退回声明顺序。"""
        declared = query.table_names()
        if stats is None or stats.stale(query.tables()):
            return Plan(declared)
        estimates = self._estimates(query, stats)
        if estimates is None:
            return Plan(declared)
        rows, selectivity = estimates
        index = {name: i for i, name in enumerate(declared)}
        pieces = [
            self._order_group(group, rows, selectivity, index)
            for group in self.components(query)
        ]
        order = self._stitch(pieces)
        return Plan(tuple(declared[i] for i in order))

    def components(self, query):
        """按等值条件把表分成互不相连的组。

        返回表名元组的元组，组内和组间都按声明顺序排列。
        """
        names = query.table_names()
        parent = {name: name for name in names}

        def find(name):
            while parent[name] != name:
                parent[name] = parent[parent[name]]
                name = parent[name]
            return name

        for t1, _, t2, _ in query.joins():
            root1, root2 = find(t1), find(t2)
            if root1 != root2:
                parent[root2] = root1
        buckets = {}
        for name in names:
            buckets.setdefault(find(name), []).append(name)
        return tuple(tuple(bucket) for bucket in buckets.values())

    @staticmethod
    def _estimates(query, stats):
        """从快照取各表行数和条件选择率，缺任何一个数就返回 None。"""
        names = query.table_names()
        rows = []
        for name in names:
            count = stats.row_count(name)
            if count is None:
                return None
            rows.append(float(count))
        index = {name: i for i, name in enumerate(names)}
        selectivity = [[1.0] * len(names) for _ in names]
        for t1, c1, t2, c2 in query.joins():
            distinct1 = stats.distinct(t1, c1)
            distinct2 = stats.distinct(t2, c2)
            if distinct1 is None or distinct2 is None:
                return None
            denom = max(distinct1, distinct2)
            sel = 1.0 / denom if denom > 0 else 0.0
            i, j = index[t1], index[t2]
            selectivity[i][j] *= sel
            selectivity[j][i] *= sel
        return rows, selectivity

    @staticmethod
    def _order_group(group, rows, selectivity, index):
        """组内重排：子集 DP 找估计探测行数最小的顺序。

        返回 (顺序（声明下标）, 整组估计行数, 该顺序的估计探测行数)。
        平手时保留声明顺序里靠前的表，保证结果确定。
        """
        members = [index[name] for name in group]
        width = len(members)
        size = 1 << width
        card = [1.0] * size
        cost = [0.0] * size
        choice = [-1] * size
        for mask in range(1, size):
            low = mask & (-mask)
            prev = mask ^ low
            table = members[low.bit_length() - 1]
            factor = rows[table]
            for other in range(width):
                if prev >> other & 1:
                    factor *= selectivity[table][members[other]]
            card[mask] = card[prev] * factor
            best = None
            for bit in range(width):
                if not mask >> bit & 1:
                    continue
                rest = mask ^ (1 << bit)
                candidate = cost[rest] + card[rest] * rows[members[bit]]
                if best is None or candidate < best:
                    best = candidate
                    choice[mask] = bit
            cost[mask] = best
        order = []
        mask = size - 1
        while mask:
            bit = choice[mask]
            order.append(members[bit])
            mask ^= 1 << bit
        order.reverse()
        return tuple(order), card[size - 1], cost[size - 1]

    @staticmethod
    def _stitch(pieces):
        """把排好序的各组叉起来：子集 DP 选组间顺序，返回声明下标序列。"""
        count = len(pieces)
        size = 1 << count
        weight = [1.0] * size
        cost = [0.0] * size
        choice = [-1] * size
        for mask in range(1, size):
            low = mask & (-mask)
            prev = mask ^ low
            weight[mask] = weight[prev] * pieces[low.bit_length() - 1][1]
            best = None
            for piece in range(count):
                if not mask >> piece & 1:
                    continue
                rest = mask ^ (1 << piece)
                candidate = cost[rest] + weight[rest] * pieces[piece][2]
                if best is None or candidate < best:
                    best = candidate
                    choice[mask] = piece
            cost[mask] = best
        picked = []
        mask = size - 1
        while mask:
            piece = choice[mask]
            picked.append(piece)
            mask ^= 1 << piece
        picked.reverse()
        order = []
        for piece in picked:
            order.extend(pieces[piece][0])
        return tuple(order)

    def __repr__(self):
        return "Planner()"
