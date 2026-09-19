"""统一渲染管线：数据(Cell/Column) -> 拼装成行 -> 输出文本。

步骤固定：建网格（全部换成 Cell）→ 纯函数算列宽 → 逐物理行拼装。
当前只有左对齐；下个版本加对齐方向/颜色标记时，改 aligned_cell
和 Cell 模型即可，管线和样式表不用动。
"""

from texttbl.models import Cell, Column
from texttbl.width import text_width, column_widths


def build_grid(headers, rows, wrap):
    """把表头和数据行规范化成 Cell 网格；grid[0] 是表头。

    格子比列少的缺格补空 Cell，保证网格是矩形。
    """
    col_count = len(headers)
    grid = [[Cell(header, wrap) for header in headers]]
    for row in rows:
        cells = []
        for i in range(col_count):
            cells.append(Cell(row[i], wrap) if i < len(row) else Cell.blank())
        grid.append(cells)
    return grid


def build_columns(grid):
    """按列聚合 Cell，纯函数算宽，产出 Column 列表。"""
    col_count = len(grid[0])
    cells_by_col = [
        [grid[row_idx][col_idx] for row_idx in range(len(grid))]
        for col_idx in range(col_count)
    ]
    return [
        Column(col_idx, width)
        for col_idx, width in enumerate(column_widths(cells_by_col))
    ]


def aligned_cell(text, column):
    """单元格内容 -> 列内一个物理行的片段（左对齐，右侧补空格）。"""
    return " " + text + " " * (column.width - text_width(text)) + " "


def render_physical_row(cells, columns, vertical):
    """一行 Cell（可能各自多行）在一个物理行号上的拼装结果。"""
    row_height = 1
    for cell in cells:
        if cell.height > row_height:
            row_height = cell.height
    lines = []
    for line_idx in range(row_height):
        parts = []
        for col_idx, column in enumerate(columns):
            text = cells[col_idx].lines[line_idx] if line_idx < cells[col_idx].height else ""
            parts.append(aligned_cell(text, column))
        lines.append(vertical + vertical.join(parts) + vertical)
    return lines


def render_table(headers, rows, style, wrap):
    """render() 的全部逻辑：网格 → 列 → 样式拼装，返回不带尾换行的文本。"""
    grid = build_grid(headers, rows, wrap)
    columns = build_columns(grid)
    widths = [column.width for column in columns]

    out_lines = []
    top = style.top_rule(widths)
    if top is not None:
        out_lines.append(top)

    out_lines.extend(render_physical_row(grid[0], columns, style.vertical))
    if style.name == "markdown":
        out_lines.append(style.header_separator(widths))
    elif len(grid) > 1:
        # 历史口径：非 markdown 空表不画表头下分隔线
        out_lines.append(style.header_separator(widths))

    for cells in grid[1:]:
        out_lines.extend(render_physical_row(cells, columns, style.vertical))

    bottom = style.bottom_rule(widths)
    if bottom is not None:
        out_lines.append(bottom)

    return "\n".join(out_lines)
