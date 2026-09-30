"""maxrect.rect: 零一网格子矩形工具（当前为改造前基线）。

本模块以零一矩阵（或带权矩阵）为底座，提供四条朴素能力：

  - 全一子矩形的面积最大值，以及取到该值的一个具体位置；
  - 全一子正方形的面积与边长最大值；
  - 带权矩阵下权值和最大的子矩形及其权值和；
  - 把每一格向上连续一的长度收进一个高度表，便于查看悬线高度的朴素口径。

当前实现全部是朴素枚举：对每一对上下边界与每一对左右边界构成四元组，逐个
候选矩形再逐格检查是否为全一（带权则逐格累计权值），是四次方以上量级。这些
做法结果正确，可规模一大就飞快变慢。另给两条独立的慢速做法用于与新路逐项
对照：按格全枚举（主路径）与直接用悬线法思想实现的一条独立路。所有输入先
校验再进入计算，非法形态在入口处快速失败。

全部只依赖标准库。
"""


class Erro(Exception):
    """本包所有异常的根，上层只认这一个。"""


class ShapeErro(Erro):
    """矩阵形态不合法：非矩阵、行不等长或单元格取值越界。"""


class ValueErro(Erro):
    """权值不是数或权值表形态不合法。"""


# 规模口径常量：朴素路径按四重循环枚举的候选矩形个数，新路按格推进的访问次数。
MONOTONIC = "monotonic"
SUSPEND = "suspend"
NAIVE = "naive"


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_matrix(grid, name="grid"):
    """校验并返回规整后的二维列表：非空行数可为零，但每行必须等长。"""
    if not isinstance(grid, (list, tuple)):
        raise ShapeErro("%s 必须是二维序列" % name)
    rows = len(grid)
    width = None
    for i, row in enumerate(grid):
        if not isinstance(row, (list, tuple)):
            raise ShapeErro("%s 第 %d 行不是序列" % (name, i))
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise ShapeErro("%s 各行长度不一致" % name)
    if width is None:
        width = 0
    return rows, width


def _check_binary(grid):
    """校验零一矩阵：只允许取值零或一。"""
    for row in grid:
        for value in row:
            if not _is_int(value) or value not in (0, 1):
                raise ShapeErro("零一矩阵的单元格只能是零或一")
    return True


class MaxRect:
    """零一（或带权）矩阵的子矩形工具，当前为改造前基线。"""

    def __init__(self, grid):
        self._rows, self._cols = _check_matrix(grid)
        self._grid = [list(row) for row in grid]
        self._valid = _check_binary(self._grid)
        # 上一次计算的统计，供规模对照使用。
        self._rect_visits = 0
        self._cell_checks = 0
        self._best_area = 0
        self._best_rect = None

    # ------------------------------------------------------------------
    # 只读属性
    # ------------------------------------------------------------------
    @property
    def rows(self):
        return self._rows

    @property
    def cols(self):
        return self._cols

    @property
    def rect_visits(self):
        """上一次朴素枚举里检查过的候选矩形个数。"""
        return self._rect_visits

    @property
    def cell_checks(self):
        """上一次朴素枚举里被逐格检查过的单元格累计次数。"""
        return self._cell_checks

    @property
    def best_area(self):
        """上一次求最大全一子矩形所得的面积。"""
        return self._best_area

    @property
    def best_rect(self):
        """上一次求最大全一子矩形所得的具体位置。"""
        return self._best_rect

    # ------------------------------------------------------------------
    # 朴素能力
    # ------------------------------------------------------------------
    def _all_one(self, top, bottom, left, right):
        """逐格检查一个候选矩形是否全一，同时累计检查次数。"""
        for r in range(top, bottom + 1):
            row = self._grid[r]
            for c in range(left, right + 1):
                self._cell_checks += 1
                if row[c] != 1:
                    return False
        return True

    def _smaller_rect(self, a, b):
        """按 (top, left, bottom, right) 字典序取较小者。"""
        return a if a <= b else b

    def _update_best(self, area, rect):
        if area > self._best_area:
            self._best_area = area
            self._best_rect = rect
        elif area == self._best_area and self._best_rect is not None:
            self._best_rect = self._smaller_rect(self._best_rect, rect)

    def brute_max_rect(self):
        """枚举全部上下左右四元组，逐格验证全一，求最大面积与一个具体位置。

        返回 (面积, (顶行, 左列, 底行, 右列))，面积为零时位置为 None。
        """
        self._rect_visits = 0
        self._cell_checks = 0
        self._best_area = 0
        self._best_rect = None
        for top in range(self._rows):
            for bottom in range(top, self._rows):
                for left in range(self._cols):
                    for right in range(left, self._cols):
                        self._rect_visits += 1
                        if self._all_one(top, bottom, left, right):
                            area = (bottom - top + 1) * (right - left + 1)
                            self._update_best(area, (top, left, bottom, right))
        return self._best_area, self._best_rect

    def brute_max_square(self):
        """枚举全部正方形候选，逐格验证全一，求最大边长与面积。"""
        self._rect_visits = 0
        self._cell_checks = 0
        best_side = 0
        for top in range(self._rows):
            for left in range(self._cols):
                limit = min(self._rows - top, self._cols - left)
                for side in range(1, limit + 1):
                    self._rect_visits += 1
                    if self._all_one(top, top + side - 1, left, left + side - 1):
                        if side > best_side:
                            best_side = side
        return best_side * best_side, best_side

    def brute_max_weight(self, weight):
        """枚举全部候选矩形，逐格累计权值，求最大权值和与一个具体位置。"""
        wrows, wcols = _check_matrix(weight, "weight")
        if wrows != self._rows or wcols != self._cols:
            raise ValueErro("权值表形状与网格不一致")
        for row in weight:
            for value in row:
                if not _is_number(value):
                    raise ValueErro("权值必须是数")
        self._rect_visits = 0
        self._cell_checks = 0
        best_sum = None
        best_rect = None
        for top in range(self._rows):
            for bottom in range(top, self._rows):
                for left in range(self._cols):
                    for right in range(left, self._cols):
                        self._rect_visits += 1
                        total = 0
                        for r in range(top, bottom + 1):
                            row = weight[r]
                            for c in range(left, right + 1):
                                self._cell_checks += 1
                                total += row[c]
                        if best_sum is None or total > best_sum:
                            best_sum = total
                            best_rect = (top, left, bottom, right)
                        elif total == best_sum:
                            best_rect = self._smaller_rect(best_rect, (top, left, bottom, right))
        if best_sum is None:
            best_sum = 0
        return best_sum, best_rect

    def simple_heights(self):
        """朴素地在每一格向上数连续一的长度，返回高度表。

        对每一格都从头向上逐格数，是平方以上量级，但结果直观。
        """
        heights = [[0] * self._cols for _ in range(self._rows)]
        for r in range(self._rows):
            for c in range(self._cols):
                if self._grid[r][c] == 1:
                    h = 0
                    rr = r
                    while rr >= 0 and self._grid[rr][c] == 1:
                        h += 1
                        rr -= 1
                    heights[r][c] = h
        return heights

    # ------------------------------------------------------------------
    # 独立做法：直接用悬线法思想实现的一条慢速路
    # ------------------------------------------------------------------
    def independent_suspend(self):
        """独立做法一：对每一格向上数悬线高度，再向左右尽量扩展求最大面积。

        返回 (面积, 位置)，与主路径口径一致但完全独立成路，不与主路径互相调用。
        """
        if self._rows == 0 or self._cols == 0:
            return 0, None
        best_area = 0
        best_rect = None
        for r in range(self._rows):
            for c in range(self._cols):
                if self._grid[r][c] != 1:
                    continue
                top = r
                while top - 1 >= 0 and self._grid[top - 1][c] == 1:
                    top -= 1
                height = r - top + 1
                left = c
                right = c
                while left - 1 >= 0 and self._column_all_one(left - 1, top, r):
                    left -= 1
                while right + 1 < self._cols and self._column_all_one(right + 1, top, r):
                    right += 1
                area = height * (right - left + 1)
                rect = (top, left, r, right)
                if area > best_area:
                    best_area = area
                    best_rect = rect
                elif area == best_area and best_rect is not None:
                    best_rect = min(best_rect, rect)
        return best_area, best_rect

    def _column_all_one(self, col, top, bottom):
        for r in range(top, bottom + 1):
            if self._grid[r][col] != 1:
                return False
        return True
