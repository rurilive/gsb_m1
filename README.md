# qmini

内存表的迷你查询引擎，单进程内嵌，纯标准库。给内部取数脚本提供够用的
SQL 子集：parse -> 计划树 -> 迭代器执行 -> explain。

## 模块结构

- `qmini/sql.py`：词法与语法分析，产出 `SelectStmt`；语法不符抛 `ParseError`
- `qmini/plan.py`：谓词 `Compare` 与计划结点 `SeqScan` / `FilterNode` /
  `SortNode` / `ProjectNode` / `LimitNode`。计划结点即迭代器（火山模型），
  逐行向子结点拉数据，`explain()` 输出树的缩进文本
- `qmini/engine.py`：`Engine` 串起 parse -> `build_plan` -> 执行；
  `execute` 物化行列表，`explain` 返回计划文本

## SQL 子集与语义

- `SELECT cols FROM table [WHERE cond] [ORDER BY col [ASC|DESC]] [LIMIT n]`
- WHERE 条件由 `col op 字面量`（op 取 `= != > >= < <=`）经 AND/OR 与
  括号任意嵌套组成，AND 优先级高于 OR
- 关键字大小写不敏感；表名、列名大小写敏感；保留字
  （SELECT/FROM/WHERE/ORDER/BY/ASC/DESC/LIMIT/AND/OR）不能作表名列名
- 字面量：整数、小数（可负）、单引号字符串（不支持转义）；不支持分号
- 比较的列必须存在，缺列抛 `KeyError(列名)`；未注册的表抛 `KeyError(表名)`
- 排序稳定，DESC 同样稳定（键相同的行保持原有先后）；LIMIT 0 输出空，
  负数或小数在解析期拒绝
- 投影输出的是新建 dict（`*` 也拷贝），过滤和排序不改写行
- 计划固定为 SeqScan -> Filter -> Sort -> Project -> Limit，
  因此 ORDER BY 的列可以不在 SELECT 列表里

## explain 格式

根结点首行，子结点每层缩进两格，越深越靠近数据源：

```
Limit[n=2]
  Project[cols=name, age]
    Sort[key=age DESC]
      Filter[age >= 30]
        SeqScan[table=users]
```

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 扩展说明

- 条件树：WHERE 解析成 `Compare`/`And`/`Or` 谓词树，`And`/`Or` 为 n 元
  结点，explain 按优先级加括号（AND 内的 OR 子树带括号）
- 等值下推：`build_plan` 里 WHERE 顶层是 AND 时先摊平嵌套 AND，再把
  等值比较（列 = 字面量）拆成独立 Filter，叠在剩余条件的 Filter 之下、
  更靠近 SeqScan 先求值；剩余条件保持原有相对顺序
- 某一组为空则不生成该层 Filter，只剩一组时保持单 Filter；OR 子树内
  的 AND 不参与拆分
