"""OrderList 与 Node 的现有行为锁定。"""

import unittest

import support  # noqa: F401  先挂 sys.path

from lruvault.nodes import Node, OrderList


class NodeTest(unittest.TestCase):

    def test_clear_breaks_everything(self):
        node = Node("k", "v")
        node.prev = Node("p", "pv")
        node.next = Node("n", "nv")
        node.clear()
        self.assertIsNone(node.key)
        self.assertIsNone(node.value)
        self.assertIsNone(node.prev)
        self.assertIsNone(node.next)


class OrderListTest(unittest.TestCase):

    def setUp(self):
        self.order = OrderList()
        self.nodes = [Node("k%d" % i, "v%d" % i) for i in range(4)]

    def test_push_front_lists_keys_from_new_to_old(self):
        for node in self.nodes:
            self.order.push_front(node)
        self.assertEqual([n.key for n in self.order.nodes()],
                         ["k3", "k2", "k1", "k0"])
        self.assertEqual(len(self.order), 4)

    def test_touch_moves_node_to_front(self):
        for node in self.nodes:
            self.order.push_front(node)
        self.order.touch(self.nodes[1])
        self.assertEqual([n.key for n in self.order.nodes()],
                         ["k1", "k3", "k2", "k0"])

    def test_touch_on_head_is_a_noop(self):
        for node in self.nodes:
            self.order.push_front(node)
        self.order.touch(self.nodes[3])
        self.assertEqual([n.key for n in self.order.nodes()],
                         ["k3", "k2", "k1", "k0"])

    def test_unlink_head_middle_tail(self):
        for node in self.nodes:
            self.order.push_front(node)
        self.order.unlink(self.nodes[3])
        self.order.unlink(self.nodes[1])
        self.order.unlink(self.nodes[0])
        self.assertEqual([n.key for n in self.order.nodes()], ["k2"])
        self.assertEqual(len(self.order), 1)
        self.assertIs(self.order.head, self.nodes[2])
        self.assertIs(self.order.tail, self.nodes[2])

    def test_unlink_clears_node_links(self):
        for node in self.nodes:
            self.order.push_front(node)
        self.order.unlink(self.nodes[2])
        self.assertIsNone(self.nodes[2].prev)
        self.assertIsNone(self.nodes[2].next)
        self.assertEqual([n.key for n in self.order.nodes()],
                         ["k3", "k1", "k0"])

    def test_pop_back_returns_oldest(self):
        self.assertIsNone(self.order.pop_back())
        for node in self.nodes:
            self.order.push_front(node)
        self.assertIs(self.order.pop_back(), self.nodes[0])
        self.assertIs(self.order.pop_back(), self.nodes[1])
        self.assertEqual([n.key for n in self.order.nodes()], ["k3", "k2"])
        self.assertIs(self.order.tail, self.nodes[2])


if __name__ == "__main__":
    unittest.main()
