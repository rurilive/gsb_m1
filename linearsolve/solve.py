"""linearsolve：线性方程组求解的朴素实现。

输入一律是整数或分数（Fraction），全程用它们精确表示，不做浮点近似。一个
线性方程组写成增广矩阵：每行是各变量系数再跟一个常数项，等号右边那列是
常数项。行数可多于变量数也可少于，方阵与非方阵都收。

本模块当前是直白写法：消元时不做主元选择，按列从左到右、行从上到下逐格
清掉，只有碰到某个位置的主元恰好为零时才到下面找一行来换；把方程组消成
上三角之后，只看最后一行是全零还是系数全零而常数项非零，据此判无解或无穷
多解；求秩靠把非零行数数一遍；求行列式直接按定义对每一行展开、递归累加
带符号的余子式，是阶乘量级。这些结果都对，但规模一大就慢，主元怎么选、
消元怎么记口径都没定下来。

规模对照的计数入口也算得笨：消元次数按三重循环逐对累加，展开次数按阶乘
直接乘出来。
"""

from fractions import Fraction

# 增广矩阵在文本里的分隔符：等号左边写各变量系数，右边写常数项，中间用一个
# 竖线隔开。非法的行、列数不一致、分隔符不合法都从 LinearSolveError 出来。
MATRIX_SEPARATOR = "|"


class LinearSolveError(Exception):
    """linearsolve 里所有可诊断错误的基类。

    message 是单行说明；position 是出错位置（行下标或列下标）；data 是出错时
    问题数据的人读摘要。上层按本基类统一捕获。
    """

    def __init__(self, message, position=0, data=""):
        super().__init__(message)
        self.message = message
        self.position = position
        self.data = data

    def __str__(self):
        return "%s (position %d)" % (self.message, self.position)


def _to_fraction(value, position=0):
    """把一个数转成分数；整数与分数都收，其余一律抛 LinearSolveError。

    布尔值当整数会静默变成零一，这里显式拒绝，避免 True 被当成 1 混进系数。
    """
    if isinstance(value, bool):
        raise LinearSolveError("数值不能是布尔值", position=position, data=str(value))
    if isinstance(value, (int, Fraction)):
        return Fraction(value)
    raise LinearSolveError("数值必须是整数或分数", position=position, data=str(value))


def _coerce_row(row, position=0):
    """把一行数逐个转成分数，返回新列表；行不是序列时抛 LinearSolveError。"""
    if row is None:
        raise LinearSolveError("行不能为空", position=position, data="")
    try:
        items = list(row)
    except TypeError:
        raise LinearSolveError("行必须是序列", position=position, data=str(row))
    if len(items) == 0:
        raise LinearSolveError("行不能为空", position=position, data="")
    return [_to_fraction(v, position) for v in items]


def check_matrix(matrix):
    """校验增广矩阵形状并返回 (行数, 列数)。

    矩阵是非空的矩形：每行都由整数或分数组成，列数至少为二（最后一列是常数
    项，前面至少一个变量列）。空矩阵、空行、各行长度不一致都抛 LinearSolveError。
    """
    if matrix is None:
        raise LinearSolveError("矩阵不能为空", position=0, data="")
    try:
        rows = list(matrix)
    except TypeError:
        raise LinearSolveError("矩阵必须是行的序列", position=0, data=str(matrix))
    if len(rows) == 0:
        raise LinearSolveError("矩阵不能为空", position=0, data="")
    width = None
    for i, row in enumerate(rows):
        coerced = _coerce_row(row, i)
        if width is None:
            width = len(coerced)
        elif len(coerced) != width:
            raise LinearSolveError("各行长度不一致", position=i, data=str(len(coerced)))
    if width < 2:
        raise LinearSolveError("增广矩阵至少要有常数项一列", position=0, data=str(width))
    return len(rows), width


def _copy_grid(matrix):
    """把矩阵拷成由分数构成的二维列表，顺带做形状校验。"""
    check_matrix(matrix)
    return [[_to_fraction(v) for v in row] for row in matrix]


def _forward_eliminate(grid):
    """最朴素的主元消元，就地把 grid 消成上三角，返回参与过的行数。

    主元按列从左到右、行从上到下地取，不做大小比较；只有当前位置主元恰好
    为零时才在下面找第一个非零行交换过来，找不到就跳过这一列。消元只往下消，
    不把主元归一，也不回代成对角，留到最后由调用方看剩下什么。
    """
    rows = len(grid)
    cols = len(grid[0]) - 1 if rows else 0
    pivot_row = 0
    for col in range(cols):
        if pivot_row >= rows:
            break
        if grid[pivot_row][col] == 0:
            swap = -1
            for r in range(pivot_row + 1, rows):
                if grid[r][col] != 0:
                    swap = r
                    break
            if swap < 0:
                continue
            grid[pivot_row], grid[swap] = grid[swap], grid[pivot_row]
        pivot = grid[pivot_row][col]
        for r in range(pivot_row + 1, rows):
            if grid[r][col] == 0:
                continue
            factor = grid[r][col] / pivot
            for c in range(col, len(grid[r])):
                grid[r][c] = grid[r][c] - factor * grid[pivot_row][c]
        pivot_row += 1
    return pivot_row


def _row_is_zero(row):
    """判断一行是否全零。"""
    for v in row:
        if v != 0:
            return False
    return True


def naive_rank(matrix):
    """朴素求增广矩阵的秩：消成上三角后数一数非零行的个数。

    只数系数部分，不含常数项那列；消元过程与正式求解用的是同一套最朴素写法，
    主元为零就往下换一行，换不到就跳列。
    """
    check_matrix(matrix)
    grid = [[_to_fraction(v) for v in row[:-1]] for row in matrix]
    rows = len(grid)
    cols = len(grid[0])
    pivot_row = 0
    for col in range(cols):
        if pivot_row >= rows:
            break
        if grid[pivot_row][col] == 0:
            swap = -1
            for r in range(pivot_row + 1, rows):
                if grid[r][col] != 0:
                    swap = r
                    break
            if swap < 0:
                continue
            grid[pivot_row], grid[swap] = grid[swap], grid[pivot_row]
        pivot = grid[pivot_row][col]
        for r in range(pivot_row + 1, rows):
            if grid[r][col] != 0:
                factor = grid[r][col] / pivot
                for c in range(col, cols):
                    grid[r][c] = grid[r][c] - factor * grid[pivot_row][c]
        pivot_row += 1
    return sum(0 if _row_is_zero(row) else 1 for row in grid)


def naive_is_consistent(matrix):
    """朴素判定增广矩阵对应的方程组有没有解。

    消成上三角后逐行看：系数与常数项都为零是同义反复，跳过；系数全零而常数
    项非零就矛盾，返回假。全部行都过关就返回真（此时可能是唯一解也可能是无穷
    多解，本函数不再区分）。
    """
    check_matrix(matrix)
    grid = _copy_grid(matrix)
    _forward_eliminate(grid)
    for row in grid:
        coeffs = row[:-1]
        rhs = row[-1]
        if _row_is_zero(coeffs) and rhs != 0:
            return False
    return True


def naive_solve_matrix(matrix):
    """朴素求解增广矩阵，返回 (状态, 解) 二元组。

    状态取唯一解、无穷多解、无解三者之一。唯一解时返回按变量顺序排列的解，
    元素是分数；无穷多解与无解时解为 None。判定只靠消元后看最后一行，不给出
    自由变量，也不给解空间的具体形状。
    """
    rows, width = check_matrix(matrix)
    grid = _copy_grid(matrix)
    pivot_row = _forward_eliminate(grid)
    cols = width - 1
    for row in grid:
        if _row_is_zero(row[:-1]) and row[-1] != 0:
            return "无解", None
    if pivot_row < cols:
        return "无穷多解", None
    solution = [Fraction(0)] * cols
    for i in range(cols - 1, -1, -1):
        pivot = grid[i][i]
        acc = grid[i][cols]
        for j in range(i + 1, cols):
            acc = acc - grid[i][j] * solution[j]
        solution[i] = acc / pivot
    return "唯一解", solution


def naive_solve(matrix):
    """朴素求解的便捷入口，只返回解。

    唯一解返回按变量顺序排列的解；无穷多解与无解都返回 None，调用方若想区分
    这两种情形要改用 naive_solve_matrix。
    """
    status, solution = naive_solve_matrix(matrix)
    if status == "唯一解":
        return solution
    return None


def naive_free_symbols(matrix):
    """朴素挑出的自由变量符号下标。

    做法是全零列即自由：扫一遍系数部分，哪一列整列都是零就算一个自由变量，
    其余列都当成主元列。这只在消元前、且主元没有重排时看着对，遇到需要换列或
    主元落空的情形会数与实际不符。返回一组变量下标。
    """
    rows, cols = check_matrix(matrix)
    width = cols - 1
    grid = [[_to_fraction(v) for v in row[:width]] for row in matrix]
    free = []
    for c in range(width):
        if all(grid[r][c] == 0 for r in range(rows)):
            free.append(c)
    return free


def naive_determinant(matrix):
    """朴素求行列式：按定义对第一行展开、递归累加带符号的余子式。

    对 n 阶方阵做 n 次递归，每次再展开 n 减一阶，整体是阶乘量级；结果用分数
    精确表示。非方阵、空矩阵一律抛 LinearSolveError。
    """
    rows, width = check_matrix(matrix)
    if width != rows + 1:
        raise LinearSolveError("行列式只对方阵有定义", position=0, data=str(width))
    if rows == 0:
        raise LinearSolveError("空矩阵没有行列式", position=0, data="")
    grid = [[_to_fraction(v) for v in row[:-1]] for row in matrix]
    return _laplace(grid)


def _laplace(grid):
    """递归展开求行列式：零阶为一，一阶取唯一元素，高阶对第一行逐项展开。"""
    n = len(grid)
    if n == 0:
        return Fraction(1)
    if n == 1:
        return grid[0][0]
    total = Fraction(0)
    for c in range(n):
        if grid[0][c] == 0:
            continue
        minor = [row[:c] + row[c + 1:] for row in grid[1:]]
        term = grid[0][c] * _laplace(minor)
        if c % 2 == 1:
            term = -term
        total = total + term
    return total


def elimination_ops(rows, cols):
    """朴素估的消元比较次数：三重循环逐对待乘加，粗略按行数乘列数再乘行数。"""
    if rows <= 0 or cols <= 0:
        return 0
    return rows * cols * max(rows - 1, 0)


def expansion_ops(n):
    """朴素拉普拉斯展开的项数：n 阶按定义展开会走到的叶子项数，即 n 的阶乘。"""
    if n <= 0:
        return 1
    total = 1
    for k in range(2, n + 1):
        total *= k
    return total


def parse_matrix_text(text):
    """朴素解析矩阵文本，返回二维分数字列表；非法文本抛 LinearSolveError。

    每行一个方程，等号左边写各变量系数、右边写常数项，中间用一个竖线隔开，
    例如 1 2 | 3 表示一个变量系数为 1、2、常数项为 3 的方程。列与列之间用
    空白分隔，空行忽略。缺分隔符、左右有非数值、各行列数不一致一律报错。
    """
    if not isinstance(text, str):
        raise LinearSolveError("矩阵文本必须是字符串", position=0, data=str(text))
    grid = []
    for lineno, raw in enumerate(text.splitlines()):
        line = raw.strip()
        if line == "":
            continue
        if line.count(MATRIX_SEPARATOR) != 1:
            raise LinearSolveError("每行必须恰好有一个分隔符", position=lineno, data=line)
        left, right = line.split(MATRIX_SEPARATOR)
        coeff_tokens = left.split()
        rhs_tokens = right.split()
        if not coeff_tokens:
            raise LinearSolveError("分隔符左边缺少系数", position=lineno, data=line)
        if len(rhs_tokens) != 1:
            raise LinearSolveError("分隔符右边必须恰有一个常数项", position=lineno, data=line)
        row = []
        try:
            for token in coeff_tokens + rhs_tokens:
                row.append(Fraction(token))
        except (ValueError, ZeroDivisionError):
            raise LinearSolveError("矩阵文本里有非法数值", position=lineno, data=line)
        grid.append(row)
    if not grid:
        raise LinearSolveError("矩阵文本里没有有效行", position=0, data=text)
    return grid


def build_augmented(coefficients, constants):
    """把系数矩阵与常数项列拼成增广矩阵。

    系数矩阵是若干行，每行给出各变量系数；常数项列是与行数等长的序列。行数
    对不上、系数行长不一致一律抛 LinearSolveError。
    """
    rows, width = check_matrix([list(row) + [0] for row in coefficients]
                               if coefficients is not None else None)
    if len(constants) != rows:
        raise LinearSolveError("常数项个数与行数不符", position=0, data=str(len(constants)))
    out = []
    for i, row in enumerate(coefficients):
        out.append([_to_fraction(v) for v in row] + [_to_fraction(constants[i])])
    return out
