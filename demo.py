"""gridnav 现状演示：建图、寻路、代价与不可达。

Run with: python3 demo.py
"""

from gridnav import (bfs_path, dijkstra_path, open_map, path_cost,
                     pillared_map, random_map)


def show_path(grid, label, path):
    if path is None:
        print("%s: 不可达" % label)
        return
    cost = path_cost(grid, path)
    shown = path if len(path) <= 10 else path[:5] + ["..."] + path[-4:]
    print("%s: 步数 %d，代价 %.6f" % (label, len(path) - 1, cost))
    print("   路径 %s" % (shown,))


def main():
    print("=== 全开地图上的 BFS ===")
    grid = open_map(5, 4)
    show_path(grid, "bfs", bfs_path(grid, (0, 0), (4, 3)))

    print()
    print("=== 柱子地图：斜穿墙角受限 ===")
    grid = pillared_map(9, 8, stride=3)
    print("障碍格 %s" % (grid.blocked_cells(),))
    show_path(grid, "bfs", bfs_path(grid, (0, 0), (8, 7)))
    show_path(grid, "dijkstra", dijkstra_path(grid, (0, 0), (8, 7)))

    print()
    print("=== 随机地图：BFS 与参考最短路 ===")
    grid = random_map(9, 7, density=0.25, seed=7,
                      protected=[(0, 0), (8, 6)])
    start, goal = (0, 0), (8, 6)
    show_path(grid, "bfs", bfs_path(grid, start, goal))
    show_path(grid, "dijkstra", dijkstra_path(grid, start, goal))

    print()
    print("=== 终点被围死 ===")
    grid = open_map(5, 5)
    for cell in ((3, 3), (3, 4), (4, 3)):
        grid.set_blocked(cell[0], cell[1])
    print("障碍格 %s" % (grid.blocked_cells(),))
    show_path(grid, "bfs", bfs_path(grid, (0, 0), (4, 4)))

    # ---- 扩展演示位 ----
    # AStarPlanner 落地后，在这里补一段：随机地图上 plan 与 dijkstra_path
    # 对拍代价，再堵掉路径上的一格，用 replan 展示增量修复与 stats 里累计
    # 展开数的差值。


if __name__ == "__main__":
    main()
