"""声明层：参数在 add() 的那一刻就定型。

Spec 把一个参数的三件事一次定死：

- dest：结果字典里的键，别名推导只在这里发生一次；
- takes_value：是否吃一个 token（store / append 吃，开关不吃）；
- action：store / store_true / append / help。

SpecRegistry 负责把 Spec 列表摊成解析与渲染共用的查表结构。
以后加子命令时，每个子命令各自持有一个注册表即可，解析器本身
只需要在 token 流上先选出注册表，复用同一套 parse/render。
"""


class Spec(object):
    """一个参数（若干别名 / 一个位置参数）的定型声明。"""

    def __init__(self, names, dest=None, action="store", default=None,
                 type=None, nargs=None, help=""):
        self.names = list(names)
        self.action = action
        self.default = default
        self.type = type
        self.nargs = nargs
        self.help = help
        self.is_option = self.names[0].startswith("-")
        self.dest = derive_dest(names, dest) if self.is_option else (dest or names[0])
        self.takes_value = self.is_option and action != "help" and action != "store_true"


def derive_dest(names, explicit=None):
    """别名 -> dest 的唯一推导点。

    显式 dest 优先；否则取第一个长别名（--），连字符转下划线；
    再没有长别名就取第一个短别名去掉前导短横。
    """
    if explicit:
        return explicit
    for name in names:
        if name.startswith("--"):
            return name[2:].replace("-", "_")
    return names[0].lstrip("-")


def make_spec(names, **kw):
    return Spec(
        names,
        dest=kw.get("dest"),
        action=kw.get("action", "store"),
        default=kw.get("default"),
        type=kw.get("type"),
        nargs=kw.get("nargs"),
        help=kw.get("help", ""),
    )


def make_help_spec():
    """-h/--help 自动注册，一直挂在列表最前面。"""
    return Spec(
        ("-h", "--help"),
        dest=None,
        action="help",
        default=None,
        type=None,
        nargs=None,
        help="显示本帮助",
    )


class SpecRegistry(object):
    """Spec 列表的定型查表结构，parse 和 render 共用。"""

    def __init__(self, specs):
        self.specs = list(specs)
        self.options = {}
        self.singles = []
        self.star = None
        for spec in self.specs:
            if spec.is_option:
                for name in spec.names:
                    self.options[name] = spec
            elif spec.nargs == "*":
                self.star = spec
            else:
                self.singles.append(spec)

    def user_options(self):
        """按声明顺序返回非 help 选项（渲染用）。"""
        return [s for s in self.specs if s.is_option and s.action != "help"]
