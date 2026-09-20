"""清单读写：巡检数据在文本清单与条目元组之间转换。

清单每行一条：`name size mtime`，# 开头的行为注释，
name 允许包含空格（按最后两个数字段切分）。
"""


def parse_line(line):
    """解析一行清单，返回 (name, size, mtime)。

    空行与注释行返回 None；字段缺失或数字段非法抛 ValueError。
    """
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    parts = text.rsplit(None, 2)
    if len(parts) != 3:
        raise ValueError(f"bad manifest line: {line!r}")
    name, size, mtime = parts
    try:
        size = int(size)
    except ValueError:
        raise ValueError(f"bad manifest line: {line!r}") from None
    try:
        mtime = int(mtime)
    except ValueError:
        try:
            mtime = float(mtime)  # time.time() 产生的小数
        except ValueError:
            raise ValueError(f"bad manifest line: {line!r}") from None
    return name, size, mtime


def parse(text):
    """解析整份清单文本，跳过注释与空行。"""
    entries = []
    for line in text.splitlines():
        item = parse_line(line)
        if item is not None:
            entries.append(item)
    return entries


def dump(entries):
    """反向转换：条目元组列表 -> 清单文本（带表头注释）。"""
    lines = ["# name size mtime"]
    for name, size, mtime in entries:
        lines.append(f"{name} {size} {mtime}")
    return "\n".join(lines) + "\n"


def load(path):
    """从文件读清单，规则同 parse。"""
    with open(path, "r", encoding="utf-8") as f:
        return parse(f.read())


def save(path, entries):
    """把条目列表写成清单文件，格式同 dump。"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(dump(entries))
