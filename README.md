# texttbl

文本表格渲染器：列对齐、超长自动换行、四套边框样式。监控后台和 CLI 工具在用，2019 年上线，纯标准库，无外部依赖。

## 对外 API（不可变更）

- `Table(headers, style="ascii", wrap=0)`
  - `headers`：列名列表（非字符串会 str() 转换）
  - `style`：`ascii` / `light` / `heavy` / `markdown`
  - `wrap`：单元格换行宽度（0 或负数 = 不换行）
- `add_row(*cells) -> Table`：格子数可比列少（缺的当空串渲染），比列多抛 ValueError
- `render() -> str`：整表文本，不带尾换行

## 契约口径（历史形成，全部要保住）

- 列宽 = 全表（含表头）按显示宽取最大，左对齐右侧补空格
- 显示宽度按 len() 算，中文等宽字符也按 1 个宽
- 换行按词贪心（连续空白算一个分隔），超长词先清行再硬切；表头同样参与换行
- markdown 分隔行横线数与列宽一致；空表不画数据分隔线
- 各样式的逐字节输出以 `tests/test_table.py` 为准

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 结构说明

- `Cell` 持有原文、换行后的 `lines` 与行高 `height`（`line_at` 取某物理行文本）；`Column` 持有表头 Cell、数据 Cell 列表和列宽，内容/行高都是数据
- 宽度计算是纯函数 `compute_column_widths(columns)`，不碰全局状态；`_text_width` 的缓存由 `lru_cache` 收口（`cache_clear()` 可清），不再暴露可写的全局 dict
- 边框是样式表：`STYLES` 里每个 `BorderStyle` 声明竖线、横线字符和 top/mid/bottom 角字符，`rule()` 统一拼横线，加样式只需加一条
- `render()` 走统一管线：`_build_columns` 切块 → `compute_column_widths` 度量 → `_assemble` 拼装，数据与拼装分离
