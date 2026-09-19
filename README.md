# argmini

内部小工具共用的命令行参数解析器，2017 年随部署工具上线，十几个工具在用。
当年没用 argparse（历史原因），纯标准库，无外部依赖。

## 对外 API

- `Parser(prog, desc="")`
- `add(*names, dest=None, action="store", default=None, type=None, nargs=None, help="")`
  - names 里以 `-` 开头的是选项别名（可多个，如 `-o, --out`），其余是位置参数名
  - action：`"store"` 取值 / `"store_true"` 开关 / `"append"` 可重复收集
  - type：取值选项的转换函数（如 int），转换失败抛 ArgsError
  - nargs：位置参数 `nargs="*"` 收集全部剩余位置参数（应声明为最后一个位置参数）
  - dest 缺省取第一个长别名的名字（`-` 转 `_`），没有长别名时取短别名
- `parse(argv) -> dict`：键为 dest；argv 里出现 `-h`/`--help` 时打印帮助并抛 SystemExit(0)
- `help() -> str`：帮助文本
- 解析失败抛 `ArgsError`

## 约定

- 长选项支持 `--name value` 和 `--name=value`；短选项只吃下一个 token，原样不作解释
- `--` 之后的 token 全部按位置参数处理；单独的 `-` 是普通位置参数
- 解析结果与错误文本以 `tests/test_cliargs.py` 为准

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 结构说明

- spec 层（`spec.py`）：`add()` 时把每个参数的 dest、action、是否取值、别名表一次定死，是全仓库唯一事实来源
- parse 层（`parse.py`）：只消费 token 流并产出 dict，不推导元信息、不碰文本；遇 `-h` 抛 `HelpRequested`
- render 层（`render.py`）：只读声明表渲染帮助文本，不参与解析
- 三层经 `parser.py` 门面装配，对外 API 与输出文本不变
- 接得住子命令：声明层可按命令挂独立 `SpecBook`，parse 层在首个位置 token 分派到对应表后照旧跑，render 层分别渲染各命令帮助，三层都不用改
