"""FlatSched：朴素任务调度实现（改造前基线，纯标准库）。

这一版只有最直白的线性扫描：没有并行概念，也没有资源约束，
每次查询都从头重扫全部任务。行为被 tests/test_plan.py 锁住。
"""


class SchedError(Exception):
    """调度相关错误的统一基类。"""


class UnknownTask(SchedError):
    """引用了未登记的任务名。"""


class DuplicateTask(SchedError):
    """重复登记同一个任务名。"""


class FlatSched:
    """一组带时长与依赖的任务，用朴素扫描回答有限几个问题。"""

    def __init__(self):
        self._dur = {}
        self._deps = {}

    def add_task(self, name, dur, deps=None):
        """登记任务：时长与依赖列表，重复登记抛 DuplicateTask。"""
        if not isinstance(name, str) or not name:
            raise ValueError("task name must be a non-empty string")
        if name in self._dur:
            raise DuplicateTask("duplicate task: %s" % name)
        if not isinstance(dur, (int, float)) or isinstance(dur, bool) or dur < 0:
            raise ValueError("duration must be a non-negative number")
        deps = list(deps) if deps else []
        for dep in deps:
            if dep not in self._dur:
                raise UnknownTask("unknown dependency: %s" % dep)
        self._dur[name] = dur
        self._deps[name] = list(deps)

    def add_dep(self, name, dep):
        """后置补一条依赖边；两端都必须已登记，可以引入环。"""
        self._require(name)
        self._require(dep)
        if dep not in self._deps[name]:
            self._deps[name].append(dep)

    def tasks(self):
        """按登记顺序返回全部任务名。"""
        return list(self._dur)

    def duration(self, name):
        self._require(name)
        return self._dur[name]

    def deps_of(self, name):
        self._require(name)
        return list(self._deps[name])

    def _require(self, name):
        if name not in self._dur:
            raise UnknownTask("unknown task: %s" % name)

    def ready_tasks(self, done):
        """线性扫描：依赖都已完成的、且自身未完成的任务。"""
        done = set(done)
        out = []
        for name in self._dur:
            if name in done:
                continue
            if all(dep in done for dep in self._deps[name]):
                out.append(name)
        return out

    def topo_order(self):
        """朴素逐轮扫描：每轮找出依赖已满足且未排入的任务。"""
        placed = []
        placed_set = set()
        remaining = list(self._dur)
        while remaining:
            progressed = False
            for name in list(remaining):
                if all(dep in placed_set for dep in self._deps[name]):
                    placed.append(name)
                    placed_set.add(name)
                    remaining.remove(name)
                    progressed = True
            if not progressed:
                raise SchedError("dependency cycle detected")
        return placed

    def total_time_serial(self):
        """线性求和全部时长（串行口径）。"""
        total = 0
        for name in self._dur:
            total += self._dur[name]
        return total

    def can_finish(self, name, done):
        """递归判断：该任务的全部传递前置是否都已落在 done 里。"""
        self._require(name)
        done = set(done)

        def ancestors(node, seen):
            out = set()
            for dep in self._deps[node]:
                if dep in seen:
                    continue
                seen.add(dep)
                out.add(dep)
                out |= ancestors(dep, seen)
            return out

        return ancestors(name, {name}) <= done
