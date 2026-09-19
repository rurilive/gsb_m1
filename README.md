# templet

运营页/邮件用的迷你模板引擎：变量替换、for/if 控制结构、过滤器链、
自动 HTML 转义。单进程内嵌，纯标准库，无外部依赖。

## 模块结构

- `templet/lexer.py`：词法，源码切成 text / var（`{{ ... }}`）/ tag（`{% ... %}`）三类 token，语法符必须成对
- `templet/expr.py`：表达式子语言，递归下降解析 + 求值；支持名字/点属性/下标/比较/and/or/not，缺失值统一为 `UNDEFINED`（渲染空串、为假、比较得 False）
- `templet/filters.py`：内置过滤器表（escape/safe/upper/lower/trim/length/join/default/first）
- `templet/nodes.py`：节点树，每类节点实现 `render(out, ctx)`，渲染结果追加进 out 列表
- `templet/parser.py`：语法分析，token 流 -> 节点树，负责 for/if/else 的块配对与 var 过滤链解析
- `templet/renderer.py`：`Engine`（模板注册表 + 过滤器表 + autoescape 开关）与 `Context`（变量作用域链，push 生成子作用域）

## 渲染管线

`Engine.render_string` 把源码交给 parser 生成节点树，逐节点 `render(out, ctx)`。
`ctx.engine` 指回引擎，节点经它取过滤器表与 autoescape 设置；变量挂在
`ctx.vars`（ChainMap），for 每轮压一层子作用域，循环变量不外泄。

## 语法约定

- `{{ 表达式 }}` 输出，默认转义；过滤链任意位置出现 `| safe` 则跳过转义
- `{% for x in 表达式 %}...{% endfor %}`，支持 `for k, v in ...` 解包，长度不齐抛 TemplateError
- `{% if 条件 %}...{% else %}...{% endif %}`
- 未闭合语法符、块未配对、未知标签抛 TemplateSyntaxError；未知过滤器抛 TemplateError（均定义在 `templet/errors.py`）

## 运行

```bash
python3 demo.py                          # 渲染演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

`tests/test_template.py` 是现有行为的锁定基线。
