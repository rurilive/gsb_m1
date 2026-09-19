"""argmini 解析核心。2017 年为部署工具写的，后来十几个小工具都靠它。

两个入口：Parser.add() 声明参数，Parser.parse() 吃 argv 出 dict。
-h/--help 自动注册。解析失败抛 ArgsError，文本都被 tests 锁着。
"""

import sys


class ArgsError(Exception):
    """解析失败。"""


class Parser(object):
    def __init__(self, prog, desc=""):
        self.prog = prog
        self.desc = desc
        # -h/--help 是自动注册的，一直挂在 specs 最前面
        self._specs = [{
            "names": ["-h", "--help"],
            "dest": None,
            "action": "help",
            "default": None,
            "type": None,
            "nargs": None,
            "help": "显示本帮助",
        }]

    def add(self, *names, **kw):
        """声明参数。names 里以 - 开头的是选项别名（可多个），其余是位置参数名。"""
        if not names:
            raise ValueError("add() needs at least one name")
        self._specs.append({
            "names": list(names),
            "dest": kw.get("dest"),
            "action": kw.get("action", "store"),
            "default": kw.get("default"),
            "type": kw.get("type"),
            "nargs": kw.get("nargs"),
            "help": kw.get("help", ""),
        })
        return self

    def parse(self, argv):
        # ---- 把声明摊成查表结构（每次 parse 现搭，历史写法）----
        opt_table = {}
        singles = []
        star = None
        for s in self._specs:
            if s["names"][0].startswith("-"):
                for n in s["names"]:
                    opt_table[n] = s
            else:
                if s["nargs"] == "*":
                    star = s
                else:
                    singles.append(s)

        out = {}
        for s in self._specs:
            if not s["names"][0].startswith("-"):
                continue
            if s["action"] == "help":
                continue
            d = None
            if s["dest"]:
                d = s["dest"]
            else:
                for n in s["names"]:
                    if n.startswith("--"):
                        d = n[2:].replace("-", "_")
                        break
                if d is None:
                    d = s["names"][0].lstrip("-")
            if s["action"] == "store_true":
                out[d] = False if s["default"] is None else s["default"]
            else:
                out[d] = s["default"]

        filled = []
        i = 0
        no_more_opts = False
        while i < len(argv):
            tok = argv[i]
            if not no_more_opts and tok == "--":
                no_more_opts = True
                i += 1
                continue
            if not no_more_opts and len(tok) > 1 and tok[0] == "-":
                # ---- 选项分支 ----
                name = tok
                val = None
                has_eq = False
                if tok.startswith("--") and "=" in tok:
                    name, val = tok.split("=", 1)
                    has_eq = True
                if name not in opt_table:
                    raise ArgsError("unknown option: %s" % name)
                s = opt_table[name]
                if s["action"] == "help":
                    if has_eq:
                        raise ArgsError("%s does not take a value" % name)
                    sys.stdout.write(self.help())
                    raise SystemExit(0)
                if s["action"] == "store_true":
                    if has_eq:
                        raise ArgsError("%s does not take a value" % name)
                    d = s["dest"] or _derive_dest(s)
                    out[d] = True
                    i += 1
                    continue
                if has_eq:
                    raw = val
                    i += 1
                else:
                    if i + 1 >= len(argv):
                        raise ArgsError("missing value for %s" % name)
                    raw = argv[i + 1]
                    i += 2
                d = s["dest"] or _derive_dest(s)
                if s["action"] == "append":
                    if out[d] is s["default"]:
                        out[d] = list(s["default"]) if isinstance(s["default"], list) else []
                    out[d].append(raw)
                else:
                    if s["type"] is not None:
                        try:
                            raw = s["type"](raw)
                        except (TypeError, ValueError):
                            raise ArgsError("invalid value for %s: %r" % (name, raw))
                    out[d] = raw
                continue
            # ---- 位置参数分支 ----
            if len(filled) < len(singles):
                s = singles[len(filled)]
                filled.append(tok)
                out[s["dest"] or _derive_dest(s)] = tok
                i += 1
                continue
            if star is not None:
                d = star["dest"] or _derive_dest(star)
                if d not in out or out[d] is star["default"]:
                    out[d] = []
                out[d].append(tok)
                i += 1
                continue
            raise ArgsError("unexpected argument: %s" % tok)

        for s in singles:
            d = s["dest"] or _derive_dest(s)
            if d not in out:
                raise ArgsError("missing required argument: %s" % s["names"][0])
        if star is not None:
            d = star["dest"] or _derive_dest(star)
            if d not in out:
                out[d] = []
        return out

    def help(self):
        singles = []
        star = None
        options = []
        for s in self._specs:
            if s["names"][0].startswith("-"):
                if s["action"] != "help":
                    options.append(s)
            else:
                if s["nargs"] == "*":
                    star = s
                else:
                    singles.append(s)

        tail = []
        for s in options:
            first = s["names"][0]
            if s["action"] == "store_true":
                tail.append("[%s]" % first)
            else:
                tail.append("[%s %s]" % (first, _derive_dest(s).upper()))
        tail.append("[-h]")
        pnames = [s["names"][0] for s in singles]
        if star is not None:
            pnames.append("[%s ...]" % star["names"][0])

        lines = []
        if self.desc:
            lines.append(self.desc)
            lines.append("")
        lines.append("usage: %s %s" % (self.prog, " ".join(tail + pnames)))
        if singles or star is not None:
            lines.append("")
            lines.append("positional:")
            rows = [(s["names"][0], s["help"]) for s in singles]
            if star is not None:
                rows.append((star["names"][0], star["help"]))
            width = max(len(r[0]) for r in rows)
            for nm, hp in rows:
                if hp:
                    lines.append("  %s  %s" % (nm.ljust(width), hp))
                else:
                    lines.append("  %s" % nm.rstrip())
        lines.append("")
        lines.append("options:")
        rows = []
        for s in options:
            left = ", ".join(s["names"])
            if s["action"] != "store_true":
                left = "%s %s" % (left, _derive_dest(s).upper())
            rows.append((left, s["help"]))
        rows.append(("-h, --help", "显示本帮助"))
        width = max(len(r[0]) for r in rows)
        for nm, hp in rows:
            if hp:
                lines.append("  %s  %s" % (nm.ljust(width), hp))
            else:
                lines.append("  %s" % nm.rstrip())
        return "\n".join(lines) + "\n"


def _derive_dest(spec):
    if spec["dest"]:
        return spec["dest"]
    for n in spec["names"]:
        if n.startswith("--"):
            return n[2:].replace("-", "_")
    return spec["names"][0].lstrip("-")
