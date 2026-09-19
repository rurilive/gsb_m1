"""依赖图分层。

层号定义：无依赖的目标在第 1 层，其余目标层号 = 最大依赖层号 + 1。
同一层内没有依赖关系，是一个并行组；层内顺序保持清单声明顺序。
"""

from .errors import GraphError


def layer_targets(manifest):
    """把清单分层，返回 [[第1层目标...], [第2层目标...], ...]。

    未知依赖或依赖成环抛 GraphError。
    """
    layer_of = {}

    def resolve(name, path):
        # path: 当前 DFS 链（不含 name），用于成环报错与归属定位
        if name in layer_of:
            return layer_of[name]
        if name not in manifest.targets:
            who = f"（被 {path[-1]!r} 引用）" if path else ""
            raise GraphError(f"未知依赖 {name!r}{who}")
        if name in path:
            cycle = " -> ".join(path[path.index(name):] + [name])
            raise GraphError(f"依赖成环: {cycle}")
        layer = 0
        for dep in manifest.targets[name].deps:
            layer = max(layer, resolve(dep, path + [name]))
        layer_of[name] = layer + 1
        return layer_of[name]

    for name in manifest.order:
        resolve(name, [])

    layers = []
    for name in manifest.order:
        n = layer_of[name]
        while len(layers) < n:
            layers.append([])
        layers[n - 1].append(name)
    return layers
