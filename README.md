# lexbend

公式编辑器用的表达式词法层：全文扫描出带行列位置的 token 序列，配一个掂着文本的编辑缓冲。
纯标准库，无外部依赖。

## 用法

```python
from lexbend import TextBuffer, keys, scan

scan("a = 1.5")          # Token 列表，最后一个是 EOF
keys(scan("a = 1.5"))    # 比较视图：(种类, 原文, 起, 止, 行, 列)

buf = TextBuffer("x = 1")
buf.replace(2, 3, "==")  # 把半开区间 [2, 3) 换成 "=="，返回 (删长, 插长)
buf.scan()               # 整段重扫，编辑器每敲一键走这条路
buf.line_col(5)          # offset 处的行列
```

## 语言的形状

- 空白：空格、制表、回车，不进 token 流，行列照算；换行只认 `\n`
- 名字 `[A-Za-z_][A-Za-z0-9_]*`，数字 `12` 或 `3.5`
- 字符串 `"..."`，反斜杠可以转义下一个字符，串里不许有换行
- 行注释 `#` 到行尾（不含行尾的换行），块注释 `/* ... */` 可以跨行
- 运算符两字符优先（`==` `!=` `<=` `>=` `&&` `||` `->`），否则单字符
- 收不住的串扫到换行或文件末尾为止，token 里不含那个换行；没关的块注释
  一路吃到文件末尾；认不出的字符一字一个 error token，不跟相邻的凑团
- 文末补一个 EOF token；行列都从 1 数，列按字符数

## 模块

- `lexbend/token.py`：`Token`（kind / text / start / end / line / col，比较一律走
  `key()`）、种类常量、`keys()`
- `lexbend/scanner.py`：`scan(text)` 全量扫描；`Cursor` 是扫描游标，pos 和行列
  同步推进，可以摆在任意 token 边界上从那儿接着往后扫；`iter_tokens` 逐 token 产出
- `lexbend/buffer.py`：`TextBuffer` 揣文本，`replace` / `insert` / `delete` 改它，
  `scan()` 整段重扫，`line_col(offset)` 查行列，`scan_count` 记着累计重扫了多少次

## 现状

编辑器把每次击键翻成一次 `replace`，然后整段重扫一遍。稿子小的时候没感觉，
稿子一长，敲一个字符就把全篇 token 重造一遍，越敲越卡。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py                          # 扫描、打字、稿子铺大之后的整段重扫成本
python3 -m unittest discover -s tests    # 既有行为基线测试
```
