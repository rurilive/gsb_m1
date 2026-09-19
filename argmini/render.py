"""第三层：render 渲染层。

只把 SpecBook 画成帮助文本。不参与 token 解析，也不推导 dest：
所有信息（dest、takes_value、别名顺序）都从 Spec 读。
"""

from argmini.spec import ACTION_STORE_TRUE


def render_help(book, prog, desc):
    options = book.user_options
    help_opt = book.help_option
    singles = book.single_positionals
    star = book.star_positional

    usage_opts = []
    for spec in options:
        if spec.action == ACTION_STORE_TRUE:
            usage_opts.append("[%s]" % spec.names[0])
        else:
            usage_opts.append("[%s %s]" % (spec.names[0], spec.dest.upper()))
    usage_opts.append("[-h]")

    pnames = [spec.names[0] for spec in singles]
    if star is not None:
        pnames.append("[%s ...]" % star.names[0])

    lines = []
    if desc:
        lines.append(desc)
        lines.append("")
    lines.append("usage: %s %s" % (prog, " ".join(usage_opts + pnames)))

    positionals = list(singles)
    if star is not None:
        positionals.append(star)
    if positionals:
        lines.append("")
        lines.append("positional:")
        width = max(len(spec.names[0]) for spec in positionals)
        for spec in positionals:
            if spec.help:
                lines.append("  %s  %s" % (spec.names[0].ljust(width), spec.help))
            else:
                lines.append("  %s" % spec.names[0].rstrip())

    rows = []
    for spec in options:
        left = ", ".join(spec.names)
        if spec.action != ACTION_STORE_TRUE:
            left = "%s %s" % (left, spec.dest.upper())
        rows.append((left, spec.help))
    rows.append((", ".join(help_opt.names), help_opt.help))

    lines.append("")
    lines.append("options:")
    width = max(len(left) for left, _ in rows)
    for left, help_text in rows:
        if help_text:
            lines.append("  %s  %s" % (left.ljust(width), help_text))
        else:
            lines.append("  %s" % left.rstrip())
    return "\n".join(lines) + "\n"
