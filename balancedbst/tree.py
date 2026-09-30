"""balancedbst.tree：自平衡有序二叉树的基线（改造前的朴素实现）。

现状做法：这是一棵最普通的二叉搜索树，每个结点只有左右孩子指针，不带
任何高度、颜色或平衡因子。插入时从根开始按值大小递归下降，比结点小就
往左、否则往右，落到底就挂一个新叶子，重复键直接照挂不合并；删除时先
按值找到目标结点，若它有两个孩子就找中序后继（右子树最小值）顶替，再
把后继原位置删掉；查找同样从根按值大小一路下降。任何一次操作走过的结
点数就是这棵树当时的深度。

这套做法结果是对的，规模小时一眼能看穿，但整棵树没有任何旋转或高度维
护，树高完全取决于键的到达顺序。把键按升序或降序灌进去，树会一路往单
边挂成一条链，单次操作最坏要走过与元素个数成正比的结点，深度逼近元素
个数。非法值类型、空树取极值、删除不存在的键统一抛异常快速失败，绝不
悄悄兜底也不擅自改值。
"""


class BalancedBSTError(Exception):
    """balancedbst 全部异常的共同基类。"""


class EmptyTreeError(BalancedBSTError):
    """在空树上取无法定义结果的东西，比如极值。"""


class ValueTypeError(BalancedBSTError):
    """值不是允许的整数类型，属于调用方非法输入。"""


class KeyMissingError(BalancedBSTError):
    """删除或查找的键在树里不存在。"""


class _Node:
    """朴素结点：只有值和左右孩子，不带任何平衡信息。"""

    __slots__ = ("value", "left", "right")

    def __init__(self, value):
        self.value = value
        self.left = None
        self.right = None


class BalancedBST:
    """有序二叉搜索树（基线：一棵不做任何旋转的普通二叉搜索树）。

    允许重复键，中序序列是按值非递减排列的所有键。add 插入一个键并返回
    树的大小；remove 删除一个键的一个实例，键不存在就抛异常；contains
    判断键是否存在，find 返回命中的那个值。inorder 给出整棵树的中序序列，
    height 给出树高，min 与 max 给出最小与最大键。所有操作都从根按值大小
    逐层下降，走过的结点数由 probes 累计，直接反映这棵树当前的深度。

    基线在有序或倒序插入时会退化成一条链：树高与元素个数同阶，单次操作
    的代价也随之与元素个数同阶，没有任何机制把树高压回对数级。
    """

    def __init__(self):
        self._root = None
        self._size = 0
        self._probes = 0

    # ---- 基本查询 -------------------------------------------------

    def is_empty(self):
        """树是否为空。"""
        return self._root is None

    def size(self):
        """键的总个数，含重复键。"""
        return self._size

    def height(self):
        """树高：空树记为 0，单结点记为 1。"""
        return self._height_of(self._root)

    def _height_of(self, node):
        """朴素做法：递归下去，左右两边谁高取谁再加一。"""
        if node is None:
            return 0
        return 1 + max(self._height_of(node.left),
                       self._height_of(node.right))

    def min(self):
        """最小的键。空树直接失败。"""
        if self._root is None:
            raise EmptyTreeError("no minimum over an empty tree")
        node = self._root
        while node.left is not None:
            self._probes += 1
            node = node.left
        return node.value

    def max(self):
        """最大的键。空树直接失败。"""
        if self._root is None:
            raise EmptyTreeError("no maximum over an empty tree")
        node = self._root
        while node.right is not None:
            self._probes += 1
            node = node.right
        return node.value

    def contains(self, value):
        """键是否存在，从根按值大小逐层下降。"""
        self._check_value(value)
        node = self._root
        while node is not None:
            self._probes += 1
            if value == node.value:
                return True
            node = node.left if value < node.value else node.right
        return False

    def find(self, value):
        """返回命中的那个值，键不存在就抛异常。"""
        self._check_value(value)
        node = self._root
        while node is not None:
            self._probes += 1
            if value == node.value:
                return node.value
            node = node.left if value < node.value else node.right
        raise KeyMissingError("key not found: %r" % (value,))

    def inorder(self):
        """整棵树的中序序列，按值非递减，重复键逐个保留。"""
        out = []
        stack = []
        node = self._root
        while stack or node is not None:
            while node is not None:
                stack.append(node)
                node = node.left
            node = stack.pop()
            self._probes += 1
            out.append(node.value)
            node = node.right
        return out

    # ---- 修改 -----------------------------------------------------

    def add(self, value):
        """插入一个键，返回插入后的规模。

        基线做法：从根开始按值大小递归下降，比当前结点小就往左、否则往右，
        落到底就挂一个新叶子。重复键照挂不合并，也不做任何旋转或重平衡。
        """
        self._check_value(value)
        self._root = self._insert(self._root, value)
        self._size += 1
        return self._size

    def _insert(self, node, value):
        if node is None:
            return _Node(value)
        self._probes += 1
        if value < node.value:
            node.left = self._insert(node.left, value)
        else:
            node.right = self._insert(node.right, value)
        return node

    def remove(self, value):
        """删除一个键的一个实例，返回删除后的规模。

        基线做法：先按值大小下降找到目标结点；目标有两个孩子时，找它右子
        树的最小结点（中序后继）顶替它的值，再把后继从它原来的位置删掉，
        整棵树不做任何旋转或重平衡。键不存在就抛异常。
        """
        self._check_value(value)
        self._root, removed = self._delete(self._root, value)
        if not removed:
            raise KeyMissingError("key not found: %r" % (value,))
        self._size -= 1
        return self._size

    def _delete(self, node, value):
        if node is None:
            return None, False
        self._probes += 1
        if value < node.value:
            node.left, removed = self._delete(node.left, value)
            return node, removed
        if value > node.value:
            node.right, removed = self._delete(node.right, value)
            return node, removed
        if node.left is None:
            return node.right, True
        if node.right is None:
            return node.left, True
        successor = node.right
        while successor.left is not None:
            self._probes += 1
            successor = successor.left
        node.value = successor.value
        node.right, _ = self._delete(node.right, successor.value)
        return node, True

    # ---- 诊断 -----------------------------------------------------

    def probes(self):
        """累计走过的结点数，从实例创建起算。

        基线的访问计数：任何一次操作都要从根逐层下降到目标位置，走过的结
        点数正比于当时的树高；有序插入把树拉成链之后，这个计数会随元素个
        数线性增长。
        """
        return self._probes

    def stats(self):
        """独立快照字典，改它不影响实例。"""
        return {
            "size": self._size,
            "height": self.height(),
            "probes": self._probes,
        }

    # ---- 校验 -----------------------------------------------------

    def _check_value(self, value):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueTypeError("value must be an int, got %r"
                                 % (type(value).__name__,))
