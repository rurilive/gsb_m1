"""Small demo for the pathlib2 package.

The first block exercises the current baseline (round-after-round relaxation).
The second block is a placeholder for the priority-queue work described in the
task.
"""

from pathlib2 import NaivePath


def baseline_demo():
    graph = NaivePath({
        "a": [("b", 1), ("c", 4)],
        "b": [("c", 2), ("d", 5)],
        "c": [("d", 1)],
        "d": [],
    })
    print("nodes:", graph.nodes_list())
    print("edges:", graph.edge_count())
    print("has negative edge:", graph.has_negative())
    print("a -> d:", graph.shortest("a", "d"))
    print("a -> all:", graph.dist_all("a"))
    print("reachable a -> d:", graph.path_exists("a", "d"))


# TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    baseline_demo()
