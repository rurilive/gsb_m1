# flagr

特性开关规则引擎：文本 DSL 规则在启动时一次性编译成 matcher 树，请求
进来按上下文属性求值，产出决策与解释。单进程内嵌，纯标准库。

## 模块结构

    flagr/
    ├── errors.py     异常族：RuleCompileError（带行列位置）、UnknownFlagError
    ├── lexer.py      词法分析：text -> Token（每个记号带 line/col）
    ├── matchers.py   匹配器与组合器：Matcher 基类 + 字段匹配器 + All/Any
    ├── compiler.py   编译管线：OP_TABLE / COMBINATOR_TABLE / compile_rules
    └── engine.py     求值：FlagEngine / FlagSpec / Rule / Decision

## DSL 语法

    # 注释
    flag 开关名
    when 表达式 -> on|off
    default on|off

表达式：

- 子句：`字段 操作符 取值`，操作符 `eq ne contains gt ge lt le`；
  或 `字段 in [取值, 取值, ...]`
- 组合器：`and(表达式, 表达式, ...)`、`or(表达式, 表达式, ...)`，
  至少 2 个参数，可任意嵌套
- 取值：带引号字符串（不支持转义）、数字、`true`/`false`、裸词
  （按字符串处理）

## 编译期校验

未知操作符、未知组合器、组合器参数不足、比较器取值非数字、字符串
未闭合、重复定义开关、语法错误——全部在 `compile_rules` 时抛
`RuleCompileError`，异常带 `line`/`col`（从 1 计），文本格式
`行:列: 消息`。编译通过后求值阶段不再报错。

## 求值语义

- 同一开关的 `when` 按书写顺序求值，第一条命中的立即定决策；
  全部未命中走 `default`，没写 default 视为 off
- 字段在上下文中缺失一律判 miss，不抛异常
- 类型不符判 miss：字符串只等于字符串，布尔只等于布尔，
  数字之间 int/float 互通；比较器遇到非数字上下文值判 miss
- `Decision.trace` 按序记录每条规则的（序号, describe, 是否命中），
  `explain()` 渲染成多行文本：

      beta-ui -> on (rule#1)
        #1 or(vip eq true, age ge 18) hit

## 运行

    python3 demo.py                          # 编译 + 三种上下文求值演示
    python3 -m unittest discover -s tests -v # 行为基线测试
