"""任务树的顺序参考实现，以及随机任务树生成器。

采集管线里的活儿天然是棵树：页面任务下挂解析和下载子任务，子任务再
往下派生。这一份用单线程按后序跑完整棵树，结果和完成顺序都能拿来对拍。
"""

import random
import threading
import time


class TaskNode:
    """任务树的一个节点。

    children 里的子节点按约定先于本节点完成；work 是模拟 IO 的耗时秒数，
    由注入的 sleep 消耗；名字进结果字典，节点结果等于 tag 加子节点结果之和。
    """

    __slots__ = ("name", "children", "work", "tag")

    def __init__(self, name, children=(), work=0.0, tag=0):
        self.name = name
        self.children = tuple(children)
        self.work = work
        self.tag = tag

    def merge(self, child_values):
        return self.tag + sum(child_values)


def run_sequential(root, sleep=time.sleep, order=None):
    """单线程按后序跑完整棵树，返回 name 到结果的字典。

    order 传入列表时，按节点完成顺序把节点名追加进去。
    """
    values = {}

    def visit(node):
        child_values = [visit(child) for child in node.children]
        if node.work:
            sleep(node.work)
        value = node.merge(child_values)
        values[node.name] = value
        if order is not None:
            order.append(node.name)
        return value

    visit(root)
    return values


def random_tree(seed, depth=3, fanout=3, leaf_work=0.0):
    """生成一棵确定性的随机任务树，同一个 seed 结果一致。

    leaf_work 是叶子的模拟耗时，数字或 rng 到秒数的可调用对象皆可；
    内部节点不带耗时，每个节点最多 fanout 个孩子，也可能提前收成叶子。
    """
    rng = random.Random(seed)
    counter = [0]

    def build(level):
        name = "t%d" % counter[0]
        counter[0] += 1
        if level <= 0 or rng.random() < 0.25:
            work = leaf_work(rng) if callable(leaf_work) else leaf_work
            return TaskNode(name, (), work, rng.randrange(1, 100))
        children = tuple(
            build(level - 1) for _ in range(rng.randrange(1, fanout + 1))
        )
        return TaskNode(name, children, 0.0, rng.randrange(1, 100))

    return build(depth)


class TreeRunner:
    """把任务树交给 Pool 跑：每个节点是一个任务，子节点由父任务提交。

    跑完返回 name 到结果的字典，形状和 run_sequential 一致；sleep 注入
    用来替换真实等待，压测时可以给个假实现。
    """

    def __init__(self, pool, sleep=time.sleep):
        self._pool = pool
        self._sleep = sleep
        self._values = {}
        self._lock = threading.Lock()

    def run(self, root):
        self._values = {}
        self._pool.submit(self._visit, root).result()
        return dict(self._values)

    def _visit(self, node):
        futures = [self._pool.submit(self._visit, child) for child in node.children]
        child_values = [future.result() for future in futures]
        if node.work:
            self._sleep(node.work)
        value = node.merge(child_values)
        with self._lock:
            self._values[node.name] = value
        return value
