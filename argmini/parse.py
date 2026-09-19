"""第二层：parse 解析层。

只吃 token 流和 SpecBook，产出 dict。不推导任何元信息
（dest/取值方式全部来自 Spec），也不拼帮助文本：遇到 -h/--help
抛 HelpRequested，由门面层决定如何渲染。
"""

from argmini.errors import ArgsError
from argmini.spec import ACTION_APPEND, ACTION_HELP, ACTION_STORE_TRUE


class HelpRequested(Exception):
    """token 流里出现 -h/--help；携带当时使用的别名。"""

    def __init__(self, name):
        super(HelpRequested, self).__init__(name)
        self.name = name


def parse_args(book, argv):
    out = _seed_defaults(book)
    singles = book.single_positionals
    star = book.star_positional
    if star is not None:
        out[star.dest] = star.default

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
            i = _consume_option(book, out, argv, i)
            continue

        if filled < len(singles):
            spec = singles[filled]
            filled += 1
            out[spec.dest] = tok
            i += 1
            continue

        if star is not None:
            if out[star.dest] is star.default:
                out[star.dest] = []
            out[star.dest].append(tok)
            i += 1
            continue

        raise ArgsError("unexpected argument: %s" % tok)

    for spec in singles:
        if spec.dest not in out:
            raise ArgsError("missing required argument: %s" % spec.names[0])
    if star is not None and out[star.dest] is star.default:
        out[star.dest] = []
    return out


def _seed_defaults(book):
    out = {}
    for spec in book.user_options:
        if spec.action == ACTION_STORE_TRUE:
            out[spec.dest] = False if spec.default is None else spec.default
        else:
            out[spec.dest] = spec.default
    return out


def _consume_option(book, out, argv, i):
    tok = argv[i]
    name = tok
    raw = None
    has_eq = False
    if tok.startswith("--") and "=" in tok:
        name, raw = tok.split("=", 1)
        has_eq = True

    spec = book.lookup_option(name)
    if spec is None:
        raise ArgsError("unknown option: %s" % name)

    if spec.action == ACTION_HELP:
        if has_eq:
            raise ArgsError("%s does not take a value" % name)
        raise HelpRequested(name)

    if spec.action == ACTION_STORE_TRUE:
        if has_eq:
            raise ArgsError("%s does not take a value" % name)
        out[spec.dest] = True
        return i + 1

    if has_eq:
        next_i = i + 1
    else:
        if i + 1 >= len(argv):
            raise ArgsError("missing value for %s" % name)
        raw = argv[i + 1]
        next_i = i + 2

    if spec.action == ACTION_APPEND:
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
