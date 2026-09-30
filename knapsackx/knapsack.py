"""knapsackx 的朴素实现（改造前基线）。

容量可达集用一长条布尔格子逐格填写，最优价值用精确重量价值表逐格推进：
每处理一个物品都把当前整张表复制一份留存，容量一大、物品一多，
二重循环与逐层留存的中间表格同时膨胀，功能正确但慢且费内存。
"""


class KnapsackError(Exception):
    """本库所有异常的基类。"""


class InvalidValueError(KnapsackError, ValueError):
    """违反数值口径时抛出（负数、非整数、容量为负等）。"""


class NoSolutionError(KnapsackError, LookupError):
    """恰好装满无解、方案重建失败时抛出。"""


def _check_weight(value):
    """物品重量校验：允许为零，但不得为负、非整数或布尔。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidValueError("物品重量必须是整数")
    if value < 0:
        raise InvalidValueError("物品重量不能为负")
    return value


def _check_value(value):
    """物品价值校验：允许为零，但不得为负、非整数或布尔。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidValueError("物品价值必须是整数")
    if value < 0:
        raise InvalidValueError("物品价值不能为负")
    return value


class Knapsack:
    """零一背包的朴素实现，逐格填写容量可达集与价值表。

    reachable_set(capacity)：装法总重量不超过容量时的全部可达重量，升序列表。
    exact_fit(capacity)：恰好装满容量的一组装入方案。
    at_least(capacity)：总重量不小于容量的一组装入方案。
    best_value(capacity)：容量上界内能取到的最大总价值。
    plan_value(capacity)：取最大价值的一组装入方案。
    update_count()：上一次计算里逐格更新容量表的次数。
    """

    def __init__(self, items=()):
        self._items = []
        self._updates = 0
        for pair in items:
            self.add(pair)

    def add(self, pair):
        try:
            weight, value = pair
        except (TypeError, ValueError):
            raise InvalidValueError("物品必须是一对重量与价值")
        self._items.append((_check_weight(weight), _check_value(value)))
        self._updates = 0
        return self

    def items(self):
        return list(self._items)

    def _check_capacity(self, capacity):
        if isinstance(capacity, bool) or not isinstance(capacity, int):
            raise InvalidValueError("容量必须是整数")
        if capacity < 0:
            raise InvalidValueError("容量不能为负")
        return capacity

    def _split(self):
        """重量为零的物品无条件可取，单独拎出；其余按原下标参与表格推进。"""
        positives = []
        zeros = []
        for index, (weight, value) in enumerate(self._items):
            if weight == 0:
                zeros.append((index, weight, value))
            else:
                positives.append((index, weight, value))
        return positives, zeros

    def _build(self, capacity):
        """逐格填充布尔容量表与精确价值表，并逐层留存整份快照。

        positives 里全是正重量物品，每个物品沿容量轴从大到小逐格更新，
        处理完再把两张表各复制一份留作方案重建的回退依据，故内存随物品数乘容量增长。
        """
        positives, _zeros = self._split()
        reach = [False] * (capacity + 1)
        reach[0] = True
        table = [-1] * (capacity + 1)
        table[0] = 0
        reach_snaps = [list(reach)]
        value_snaps = [list(table)]
        updates = 0
        for _index, weight, value in positives:
            if weight <= capacity:
                for cap in range(capacity, weight - 1, -1):
                    updates += 1
                    if reach[cap - weight]:
                        reach[cap] = True
                    if table[cap - weight] >= 0:
                        candidate = table[cap - weight] + value
                        if candidate > table[cap]:
                            table[cap] = candidate
            reach_snaps.append(list(reach))
            value_snaps.append(list(table))
        self._updates = updates
        return positives, reach, table, reach_snaps, value_snaps

    def _rebuild_weight(self, positives, target, reach_snaps):
        """按留存快照从后往前回退，凑出重量恰好为 target 的正重量物品。"""
        picked = []
        remain = target
        for position in range(len(positives), 0, -1):
            index, weight, value = positives[position - 1]
            if weight > remain:
                continue
            if reach_snaps[position - 1][remain - weight]:
                picked.append((index, weight, value))
                remain -= weight
        if remain != 0:
            raise NoSolutionError("方案重建失败")
        picked.sort()
        return picked

    def reachable_set(self, capacity):
        capacity = self._check_capacity(capacity)
        _pos, reach, _table, _rs, _vs = self._build(capacity)
        return [cap for cap in range(capacity + 1) if reach[cap]]

    def update_count(self):
        return self._updates

    def best_value(self, capacity):
        capacity = self._check_capacity(capacity)
        _pos, _reach, table, _rs, _vs = self._build(capacity)
        _positives, zeros = self._split()
        base = 0
        for cap in range(capacity + 1):
            if table[cap] > base:
                base = table[cap]
        return base + sum(value for _i, _w, value in zeros)

    def exact_fit(self, capacity):
        capacity = self._check_capacity(capacity)
        positives, reach, _table, reach_snaps, _vs = self._build(capacity)
        if not reach[capacity]:
            raise NoSolutionError("恰好装满无解")
        return self._rebuild_weight(positives, capacity, reach_snaps)

    def at_least(self, capacity):
        capacity = self._check_capacity(capacity)
        total = 0
        for weight, _value in self._items:
            total += weight
        positives, reach, _table, reach_snaps, _vs = self._build(total)
        chosen = None
        for cap in range(capacity, total + 1):
            if reach[cap]:
                chosen = cap
                break
        if chosen is None:
            return []
        return self._rebuild_weight(positives, chosen, reach_snaps)

    def plan_value(self, capacity):
        capacity = self._check_capacity(capacity)
        positives, _reach, table, _rs, value_snaps = self._build(capacity)
        _positives, zeros = self._split()
        best = 0
        best_cap = 0
        for cap in range(capacity + 1):
            if table[cap] > best:
                best = table[cap]
                best_cap = cap
        total_best = best + sum(value for _i, _w, value in zeros)
        if total_best <= 0:
            return []
        picked = list(zeros)
        remain = best_cap
        for position in range(len(positives), 0, -1):
            index, weight, value = positives[position - 1]
            if weight > remain:
                continue
            previous = value_snaps[position - 1][remain - weight]
            if previous >= 0 and previous + value == value_snaps[position][remain]:
                picked.append((index, weight, value))
                remain -= weight
        picked.sort()
        return picked
