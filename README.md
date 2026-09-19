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

- `models.py`：`Cell`（文本/换行后的物理行，行高、宽度为派生数据）与 `Column`（序号+列宽），只管数据
- `width.py`：宽度纯函数 `text_width`、`column_widths`，历史口径 len()；缓存放进有界 `lru_cache` 收口，不再有谁都能写的模块级 dict
- `styles.py`：四套边框是 `STYLES` 样式表（纵向字符+角点/连接点字形+横线字符），横线由统一的 `BorderStyle.rule()` 生成
- `pipeline.py`：统一管线 `build_grid` → `build_columns` → `render_table`；对齐集中在 `aligned_cell`，加对齐方向/颜色标记只动这里和 `Cell`
- `render.py`：只剩对外的 `Table` 门面，构造参数/`add_row`/`render` 签名与输出字节完全不变
