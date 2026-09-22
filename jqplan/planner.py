"""连接顺序规划。

Planner 拿着统计快照估计中间结果的大小，按嵌套循环的探测行数口径给连接
顺序估价：前 i-1 张表的估计中间结果乘上第 i 张表的行数，逐张累加。
小表集用子集动态规划求估价最优，表太多时换贪心，保证规划耗时可控。
条件图不连通时按连接组各自排好，再按叉乘代价把组拼接起来。
统计缺了、过期了或者跟查询对不上时，整体退回查询的声明顺序。
同样的查询加同样的统计，每次拿到的计划都一样。
"""

from functools import cmp_to_key

from .engine import Plan


class Planner:
    """给出查询的执行计划。"""

    _DP_LIMIT = 12

    def plan(self, query, stats=None):
        """出计划。stats 传 None 或者统计不可用都退回声明顺序。"""
        if not self._usable(query, stats):
            return Plan(query.table_names())
        components = []
        for names in self.components(query):
            order, cost, rows = self._order_component(query, stats, names)
            components.append((order, cost, rows))
        if len(components) > 1:
            components.sort(key=cmp_to_key(self._compare_components))
        order = tuple(name for component in components for name in component[0])
        return Plan(order)

    def components(self, query):
        """按等值条件把表分成连通的组，组内组间都按声明顺序列出。"""
        names = query.table_names()
        parent = {name: name for name in names}

        def find(name):
            root = name
            while parent[root] != root:
                root = parent[root]
            while parent[name] != root:
                parent[name], name = root, parent[name]
            return root

        for t1, _, t2, _ in query.joins():
            r1, r2 = find(t1), find(t2)
            if r1 != r2:
                parent[r2] = r1
        groups = {}
        for name in names:
            groups.setdefault(find(name), []).append(name)
        return tuple(tuple(group) for group in groups.values())

    @staticmethod
    def _usable(query, stats):
        """统计能覆盖这次查询才用：没采集过、过期、缺连接列基数都算不可用。"""
        if stats is None:
            return False
        if stats.stale(query.tables()):
            return False
        for name in query.table_names():
            if stats.row_count(name) is None:
                return False
        for t1, c1, t2, c2 in query.joins():
            if stats.distinct(t1, c1) is None or stats.distinct(t2, c2) is None:
                return False
        return True

    @staticmethod
    def _compare_components(left, right):
        """叉乘相邻交换准则：left 先执行更省探测就排前面，相等保持声明顺序。"""
        _, cost_l, rows_l = left
        _, cost_r, rows_r = right
        lhs = cost_l + rows_l * cost_r
        rhs = cost_r + rows_r * cost_l
        if lhs < rhs:
            return -1
        if lhs > rhs:
            return 1
        return 0

    def _order_component(self, query, stats, names):
        """给一个连通组排顺序，返回 (顺序, 估计探测行数, 估计结果行数)。"""
        if len(names) == 1:
            rows = float(stats.row_count(names[0]))
            return names, rows, rows
        rows, divisor = self._component_model(query, stats, names)
        if len(names) <= self._DP_LIMIT:
            return self._dp_order(names, rows, divisor)
        return self._greedy_order(names, rows, divisor)

    @staticmethod
    def _component_model(query, stats, names):
        """组内行数与每对表之间的基数约简因子。"""
        index = {name: i for i, name in enumerate(names)}
        rows = [float(stats.row_count(name)) for name in names]
        divisor = [[1.0] * len(names) for _ in names]
        for t1, c1, t2, c2 in query.joins():
            i, j = index.get(t1), index.get(t2)
            if i is None or j is None:
                continue
            shrink = max(stats.distinct(t1, c1), stats.distinct(t2, c2)) or 1
            divisor[i][j] *= shrink
            divisor[j][i] *= shrink
        return rows, divisor

    @staticmethod
    def _dp_order(names, rows, divisor):
        """子集动态规划：best[掩码] 是该子集的 (最小估计探测行数, 顺序)。"""
        count = len(names)
        est_cache = {0: 1.0}

        def est_rows(mask):
            cached = est_cache.get(mask)
            if cached is not None:
                return cached
            low = mask & -mask
            i = low.bit_length() - 1
            prev = mask ^ low
            value = est_rows(prev) * rows[i]
            rest = prev
            while rest:
                low_j = rest & -rest
                value /= divisor[i][low_j.bit_length() - 1]
                rest ^= low_j
            est_cache[mask] = value
            return value

        best = {0: (0.0, ())}
        for mask in range(1 << count):
            cost, order = best[mask]
            base = est_rows(mask)
            for i in range(count):
                bit = 1 << i
                if mask & bit:
                    continue
                new_mask = mask | bit
                new_cost = cost + base * rows[i]
                current = best.get(new_mask)
                if current is None or new_cost < current[0]:
                    best[new_mask] = (new_cost, order + (i,))
        full = (1 << count) - 1
        cost, order = best[full]
        return tuple(names[i] for i in order), cost, est_rows(full)

    @staticmethod
    def _greedy_order(names, rows, divisor):
        """表太多时的贪心：每步选让中间结果最小的表，平局取小下标。"""
        count = len(names)
        placed = []
        remaining = list(range(count))
        est = 1.0
        cost = 0.0
        while remaining:

            def est_after(i, est=est, placed=placed):
                value = est * rows[i]
                for j in placed:
                    value /= divisor[i][j]
                return value

            pick = min(remaining, key=lambda i: (est_after(i), est * rows[i], i))
            cost += est * rows[pick]
            est = est_after(pick)
            placed.append(pick)
            remaining.remove(pick)
        return tuple(names[i] for i in placed), cost, est

    def __repr__(self):
        return "Planner()"
