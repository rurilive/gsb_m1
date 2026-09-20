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
    """依赖关系成环，压不出执行序。

    nodes 按顺序列出环上的节点（首尾不重复）。
    """

    def __init__(self, message="dependency cycle detected", nodes=()):
        super(CycleError, self).__init__(message)
        self.nodes = tuple(nodes)


class Job(object):
    """一个待执行的节点。

    fn 是无参可调用对象，返回值记进 RunReport.results。
    retries 是失败后的额外尝试次数；timeout 是单次尝试的墙钟秒数，
    None 表示不限时。
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

        retries：节点抛异常或超时后的额外尝试次数，默认 0（只跑一次）。
        timeout：单次尝试的墙钟秒数，超时记 TimeoutError 并按失败处理。
        """
        if name in self._jobs:
            raise DuplicateJobError("job %r already declared" % name)
        if not isinstance(retries, int) or retries < 0:
            raise ValueError("retries must be a non-negative int, got %r"
                             % (retries,))
        if timeout is not None:
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                raise ValueError("timeout must be a positive number or None, "
                                 "got %r" % (timeout,))
        unique = []
        for dep in deps:
            if dep not in unique:
                unique.append(dep)
        job = Job(name, fn, tuple(unique), retries, timeout)
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
        """依赖在前、结果确定的执行序。依赖悬空报 UnknownDepError，成环报 CycleError。"""
        for name, job in self._jobs.items():
            for dep in job.deps:
                if dep not in self._jobs:
                    raise UnknownDepError(
                        "job %r depends on unknown %r" % (name, dep))
        post = []
        done = set()
        # 迭代版后序 DFS：十万级链路压序时递归版会撞 RecursionError。
        # 栈帧 (节点, 待遍历的下游游标)，语义与原来的 _walk 递归完全一致。
        for name in self._jobs:
            if name in done:
                continue
            stack = [(name, 0)]
            on_path = [name]
            on_path_set = {name}
            while stack:
                current, index = stack[-1]
                dependents = self._dependents.get(current, ())
                if index < len(dependents):
                    nxt = dependents[index]
                    stack[-1] = (current, index + 1)
                    if nxt in done:
                        continue
                    if nxt in on_path_set:
                        start = on_path.index(nxt)
                        cycle = on_path[start:]
                        raise CycleError(
                            "dependency cycle detected: %s"
                            % " -> ".join(cycle + [nxt]),
                            nodes=cycle)
                    stack.append((nxt, 0))
                    on_path.append(nxt)
                    on_path_set.add(nxt)
                else:
                    stack.pop()
                    on_path_set.discard(on_path.pop())
                    done.add(current)
                    post.append(current)
        post.reverse()
        return post
