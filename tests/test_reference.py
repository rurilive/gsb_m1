"""顺序参考实现与随机树生成器的基线。"""

import unittest

from stealpool.reference import TaskNode, random_tree, run_sequential


def flatten(node):
    return (
        node.name,
        node.tag,
        node.work,
        tuple(flatten(child) for child in node.children),
    )


class SequentialTest(unittest.TestCase):
    def test_post_order_values(self):
        tree = TaskNode(
            "page",
            (
                TaskNode("links", tag=2),
                TaskNode("images", (TaskNode("thumb", tag=3),), tag=5),
            ),
            tag=100,
        )
        order = []
        values = run_sequential(tree, sleep=lambda seconds: None, order=order)
        self.assertEqual(values, {"links": 2, "thumb": 3, "images": 8, "page": 110})
        self.assertEqual(order, ["links", "thumb", "images", "page"])

    def test_work_is_consumed_through_injection(self):
        tree = TaskNode("root", (TaskNode("a", work=0.25), TaskNode("b", work=0.5)))
        slept = []
        run_sequential(tree, sleep=slept.append)
        self.assertEqual(sorted(slept), [0.25, 0.5])


class RandomTreeTest(unittest.TestCase):
    def test_same_seed_same_tree_different_seed_differs(self):
        one = random_tree(5, depth=3, fanout=2)
        self.assertEqual(flatten(one), flatten(random_tree(5, depth=3, fanout=2)))
        self.assertNotEqual(flatten(one), flatten(random_tree(6, depth=3, fanout=2)))

    def test_leaf_work_sampling(self):
        tree = random_tree(9, depth=2, fanout=3, leaf_work=lambda rng: rng.choice([0.1, 0.2]))
        slept = []
        run_sequential(tree, sleep=slept.append)
        self.assertTrue(slept)
        self.assertTrue(all(seconds in (0.1, 0.2) for seconds in slept))
        slept = []
        run_sequential(random_tree(3, depth=2, fanout=2), sleep=slept.append)
        self.assertEqual(slept, [])


if __name__ == "__main__":
    unittest.main()
