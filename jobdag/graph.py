"""依赖图定义与拓扑排序。

JobGraph 按声明顺序记账节点，依赖允许先引用后声明（补数流水线里常见：
下游先写好，上游的上游过两天才补进来）。topo_order() 把图压成一个确定的
执行序：任一节点都排在它引用的依赖之后。
"""


class GraphError(Exception):
    """图定义相关的错误基类。"""


class DuplicateJobError(GraphError):
    """同名节点被声明了两次。"""


class UnknownDepError(GraphError):
    """依赖引用了一个始终没有声明的节点。"""


class CycleError(GraphError):
    """依赖关系成环，压不出执行序。"""


class Job(object):
    """一个待执行的节点。

    fn 是无参可调用对象，返回值记进 RunReport.results。
    retries 是失败后允许的重试次数，timeout 是单次尝试的秒数上限；
    两者由 Scheduler 使用，SequentialRunner 忽略。
    """

    __slots__ = ("name", "fn", "deps", "retries", "timeout")

    def __init__(self, name, fn, deps, retries=0, timeout=None):
        self.name = name
        self.fn = fn
        self.deps = deps
        self.retries = retries
        self.timeout = timeout

    def __repr__(self):
        return "Job(%r, deps=%r)" % (self.name, list(self.deps))


class JobGraph(object):
    """节点集合，名字唯一，按声明顺序保存。"""

    def __init__(self):
        self._jobs = {}
        self._dependents = {}

    def add(self, name, fn, deps=(), retries=0, timeout=None):
        """声明一个节点。重复名字报错；依赖此时可以不满足，留到压序时校验。

        retries 是失败后的重试次数（非负整数），timeout 是单次尝试的
        秒数上限（None 表示不限），都由 Scheduler 在运行时兑现。
        """
        if name in self._jobs:
            raise DuplicateJobError("job %r already declared" % name)
        if retries < 0:
            raise ValueError("retries must be >= 0, got %r" % retries)
        if timeout is not None and timeout <= 0:
            raise ValueError("timeout must be > 0, got %r" % timeout)
        unique = []
        for dep in deps:
            if dep not in unique:
                unique.append(dep)
        job = Job(name, fn, tuple(unique), retries=retries, timeout=timeout)
        self._jobs[name] = job
        for dep in unique:
            self._dependents.setdefault(dep, []).append(name)
        return job

    def job(self, name):
        return self._jobs[name]

    def names(self):
        return list(self._jobs)

    def __contains__(self, name):
        return name in self._jobs

    def __len__(self):
        return len(self._jobs)

    def topo_order(self):
        """依赖在前、结果确定的执行序。依赖悬空报 UnknownDepError，成环报 CycleError。

        迭代式深度优先，十万级节点不会触 RecursionError。
        """
        for name, job in self._jobs.items():
            for dep in job.deps:
                if dep not in self._jobs:
                    raise UnknownDepError(
                        "job %r depends on unknown %r" % (name, dep))
        post = []
        done = set()
        for root in self._jobs:
            if root in done:
                continue
            path = [root]
            on_path = {root}
            stack = [(root, iter(self._dependents.get(root, ())))]
            while stack:
                node, dependents = stack[-1]
                descended = False
                for dependent in dependents:
                    if dependent in done:
                        continue
                    if dependent in on_path:
                        cycle = path[path.index(dependent):] + [dependent]
                        raise CycleError(
                            "dependency cycle detected: %s"
                            % " -> ".join(repr(item) for item in cycle))
                    path.append(dependent)
                    on_path.add(dependent)
                    stack.append(
                        (dependent, iter(self._dependents.get(dependent, ()))))
                    descended = True
                    break
                if not descended:
                    stack.pop()
                    path.pop()
                    on_path.discard(node)
                    done.add(node)
                    post.append(node)
        post.reverse()
        return post
