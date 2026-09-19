"""解析层：只吃 token 流，不碰声明推导、不碰帮助文本。

输入是 SpecRegistry + argv，输出是结果 dict。所有“这个选项叫什么、
取不取值、结果键是什么”的问题都在声明层定死，这里只做状态机：

- 看到 -h/--help 抛 HelpRequested（由门面决定打印帮助并退出）；
- 选项按 spec.takes_value 决定是否消费下一个 token；
- 其余 token 按顺序填位置参数，填满后进 nargs="*"；
- 任何不符合预期的 token 抛 ArgsError，文本与历史版本逐字一致。
"""


class ArgsError(Exception):
    """解析失败。"""


class HelpRequested(Exception):
    """argv 里出现了 -h/--help。门面负责打印帮助并 SystemExit(0)。"""


def parse_tokens(registry, argv):
    out = _defaults(registry)

    filled = 0
    i = 0
    no_more_opts = False
    while i < len(argv):
        tok = argv[i]
        if not no_more_opts and tok == "--":
            no_more_opts = True
            i += 1
            continue
        if not no_more_opts and len(tok) > 1 and tok[0] == "-":
            i = _consume_option(registry, argv, i, tok, out)
            continue
        _consume_positional(registry, tok, filled, out)
        filled += 1
        i += 1

    for spec in registry.singles:
        if spec.dest not in out:
            raise ArgsError("missing required argument: %s" % spec.names[0])
    if registry.star is not None and registry.star.dest not in out:
        out[registry.star.dest] = []
    return out


def _defaults(registry):
    """选项默认值；位置参数（含 nargs="*"）不预置，靠填充/收尾决定。"""
    out = {}
    for spec in registry.specs:
        if not spec.is_option or spec.action == "help":
            continue
        if spec.action == "store_true":
            out[spec.dest] = False if spec.default is None else spec.default
        else:
            out[spec.dest] = spec.default
    return out


def _consume_option(registry, argv, i, tok, out):
    name = tok
    val = None
    has_eq = False
    if tok.startswith("--") and "=" in tok:
        name, val = tok.split("=", 1)
        has_eq = True

    spec = registry.options.get(name)
    if spec is None:
        raise ArgsError("unknown option: %s" % name)

    if not spec.takes_value:
        if has_eq:
            raise ArgsError("%s does not take a value" % name)
        if spec.action == "help":
            raise HelpRequested(name)
        out[spec.dest] = True
        return i + 1

    if has_eq:
        raw = val
        next_i = i + 1
    else:
        if i + 1 >= len(argv):
            raise ArgsError("missing value for %s" % name)
        raw = argv[i + 1]
        next_i = i + 2

    if spec.action == "append":
        # 用 is 判断，确保只在“仍是声明默认值”时复制一份；
        # 短选项吃下一个 token 时原样保留，不做任何解释。
        if out[spec.dest] is spec.default:
            out[spec.dest] = list(spec.default) if isinstance(spec.default, list) else []
        out[spec.dest].append(raw)
    else:
        if spec.type is not None:
            try:
                raw = spec.type(raw)
            except (TypeError, ValueError):
                raise ArgsError("invalid value for %s: %r" % (name, raw))
        out[spec.dest] = raw
    return next_i


def _consume_positional(registry, tok, filled, out):
    if filled < len(registry.singles):
        spec = registry.singles[filled]
        out[spec.dest] = tok
        return
    if registry.star is not None:
        spec = registry.star
        if spec.dest not in out or out[spec.dest] is spec.default:
            out[spec.dest] = []
        out[spec.dest].append(tok)
        return
    raise ArgsError("unexpected argument: %s" % tok)
