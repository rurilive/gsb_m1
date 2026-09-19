"""渲染层：只把 SpecRegistry 拼成帮助文本，不参与任何解析。

文本格式（含空格与空行）被 tests/test_cliargs.py 逐字锁定：

- 有 desc 时先放 desc 和一个空行；
- usage 行里选项按声明顺序排列（store_true 只显名字，其余带 DEST），
  固定追加 [-h]，再跟位置参数，nargs="*" 显示为 [name ...]；
- 只有存在位置参数时才出 positional 段；
- options 段每行对齐到最长左列，固定以 -h, --help 收尾。
"""


def render_help(prog, desc, registry):
    lines = []
    if desc:
        lines.append(desc)
        lines.append("")

    usage_parts = [_usage_option(spec) for spec in registry.user_options()]
    usage_parts.append("[-h]")
    usage_parts.extend(spec.names[0] for spec in registry.singles)
    if registry.star is not None:
        usage_parts.append("[%s ...]" % registry.star.names[0])
    lines.append("usage: %s %s" % (prog, " ".join(usage_parts)))

    if registry.singles or registry.star is not None:
        lines.append("")
        lines.append("positional:")
        rows = [(spec.names[0], spec.help) for spec in registry.singles]
        if registry.star is not None:
            rows.append((registry.star.names[0], registry.star.help))
        lines.extend(_format_rows(rows))

    lines.append("")
    lines.append("options:")
    rows = []
    for spec in registry.user_options():
        left = ", ".join(spec.names)
        if spec.takes_value:
            left = "%s %s" % (left, spec.dest.upper())
        rows.append((left, spec.help))
    rows.append(("-h, --help", "显示本帮助"))
    lines.extend(_format_rows(rows))

    return "\n".join(lines) + "\n"


def _usage_option(spec):
    if not spec.takes_value:
        return "[%s]" % spec.names[0]
    return "[%s %s]" % (spec.names[0], spec.dest.upper())


def _format_rows(rows):
    width = max(len(left) for left, _ in rows)
    formatted = []
    for left, text in rows:
        if text:
            formatted.append("  %s  %s" % (left.ljust(width), text))
        else:
            formatted.append("  %s" % left.rstrip())
    return formatted
