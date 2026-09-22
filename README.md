# rexflow

日志检索用的小正则引擎，纯标准库，无外部依赖。

## 现状

- `rexflow/parser.py`：`parse(pattern)` 把模式串解析成节点树
  （`Seq`、`Char`、`Star`），出错抛带下标的 `PatternError`
- `rexflow/matcher.py`：递归回溯执行；`Pattern.fullmatch(text)` 整串匹配，
  `Pattern.search(text)` 在文本里找第一处匹配，`Match` 给出整体区间的
  `start`、`end`、`span`、`group`，`naive_search` 是从每个起点重试的搜索
- `rexflow/errors.py`：`PatternError(message, pattern, pos)`，`pos` 是模式串
  里出错字符的下标（从 0 起）

目前语法只有字面量和星号，其余元字符遇到会明确报错并指出位置；
执行是递归回溯，搜索从每个起点把整棵树重跑，长文本与嵌套量词下的
实测代价见 `demo.py` 的输出。编译入口是 `rexflow.compile(pattern)`。

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

`tests/` 是行为基线，锁住现有语义，改实现时保持全绿。

## 约定

纯标准库，不引入三方依赖；基线测试不做修改。
