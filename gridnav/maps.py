"""常用地图构造器；随机地图只由 seed 决定，跨进程可复现。"""

import random

from gridnav.grid import Grid


def open_map(width, height):
    """全开地图，没有任何障碍。"""
    return Grid(width, height)


def random_map(width, height, density=0.3, seed=0, protected=()):
    """按行优先逐格铺随机障碍，密度为每格被堵的概率。

    protected 里的格子强制留空，常用来保住起终点。障碍集合只取决于
    width、height、density、seed 和 protected，与调用顺序无关。
    """
    rng = random.Random(seed)
    keep = {(int(x), int(y)) for x, y in protected}
    blocked = []
    for y in range(height):
        for x in range(width):
            if (x, y) in keep:
                continue
            if rng.random() < density:
                blocked.append((x, y))
    return Grid(width, height, blocked)


def pillared_map(width, height, stride=4):
    """每 stride 格在 (2, 2) 偏移处立一根柱子，用于演示贴墙与斜穿限制。"""
    blocked = []
    for y in range(2, height, stride):
        for x in range(2, width, stride):
            blocked.append((x, y))
    return Grid(width, height, blocked)
