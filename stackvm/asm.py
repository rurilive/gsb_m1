"""汇编与反汇编：文本程序 <-> 字节码。

文本格式：每行一条指令（`助记符 [操作数]`），`#` 后为注释，空行忽略；
`标签:` 单独成行，指向其后第一条指令的字节偏移，操作数处可直接写标签名。
disasm 输出带 4 位十六进制偏移列，assemble 遇到该列会自动跳过，因此
disasm 的输出可以再喂回 assemble。
"""

from stackvm.errors import VmError
from stackvm.opcodes import BY_CODE, OPS


def assemble(source):
    """文本程序 -> 字节码。两遍处理：先算偏移，再生成编码。"""
    items, label_items = _scan(source)
    offsets = []
    pc = 0
    for _, name, _ in items:
        offsets.append(pc)
        pc += 3 if OPS[name][1] == "u16" else 1
    labels = {name: offsets[idx] for name, idx in label_items.items()}
    out = bytearray()
    for (lineno, name, operand), pc in zip(items, offsets):
        code, layout = OPS[name]
        out.append(code)
        if layout == "u16":
            out += _operand(lineno, name, operand, labels).to_bytes(2, "little")
    return bytes(out)


def _scan(source):
    items, label_items = [], {}
    for lineno, raw in enumerate(source.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.endswith(":") and " " not in line:
            label_items[line[:-1]] = len(items)
            continue
        fields = line.split()
        if len(fields) > 1 and len(fields[0]) == 4 and _is_hex(fields[0]):
            fields = fields[1:]  # 跳过 disasm 的偏移列
        name = fields[0]
        if name not in OPS:
            raise VmError("第 %d 行未知指令 %r" % (lineno, name))
        if len(fields) > 2:
            raise VmError("第 %d 行指令多余字段: %r" % (lineno, line))
        operand = fields[1] if len(fields) > 1 else None
        if operand is None and OPS[name][1] == "u16":
            raise VmError("第 %d 行 %s 缺少操作数" % (lineno, name))
        if operand is not None and OPS[name][1] == "":
            raise VmError("第 %d 行 %s 不接受操作数" % (lineno, name))
        items.append((lineno, name, operand))
    return items, label_items


def _is_hex(text):
    try:
        int(text, 16)
        return True
    except ValueError:
        return False


def _operand(lineno, name, operand, labels):
    if operand in labels:
        return labels[operand]
    try:
        value = int(operand, 10)
    except (TypeError, ValueError):
        raise VmError("第 %d 行 %s 操作数不是整数或标签: %r" % (lineno, name, operand))
    if not 0 <= value <= 0xFFFF:
        raise VmError("第 %d 行 %s 操作数超出 u16: %d" % (lineno, name, value))
    return value


def disasm(code):
    """字节码 -> 文本程序，每行 `偏移  助记符 [操作数]`。"""
    lines = []
    pc = 0
    while pc < len(code):
        op = code[pc]
        if op not in BY_CODE:
            raise VmError("偏移 %#06x 处未知操作码 %#04x" % (pc, op))
        name, layout = BY_CODE[op]
        if layout == "u16":
            if pc + 3 > len(code):
                raise VmError("偏移 %#06x 处 %s 操作数被截断" % (pc, name))
            lines.append("%04x  %s %d" % (pc, name, int.from_bytes(code[pc + 1:pc + 3], "little")))
            pc += 3
        else:
            lines.append("%04x  %s" % (pc, name))
            pc += 1
    return "\n".join(lines)
