"""第一层：spec 声明层。

add() 一调用，dest、取值方式（takes_value）、action、kind 就在这里
一次定死；parse 和 render 都只读 Spec，不再各自推导。
"""

ACTION_STORE = "store"
ACTION_STORE_TRUE = "store_true"
ACTION_APPEND = "append"
ACTION_HELP = "help"


def derive_dest(names, explicit):
    """dest 推导规则：显式 dest 优先；否则第一个长别名；再否则第一个短别名。"""
    if explicit:
        return explicit
    for name in names:
        if name.startswith("--"):
            return name[2:].replace("-", "_")
    return names[0].lstrip("-")


class Spec(object):
    """一条参数声明。构造后属性全部定型，全仓库唯一的事实来源。"""

    def __init__(self, names, dest, action, default, value_type, nargs, help_text):
        self.names = list(names)
        self.dest = dest
        self.action = action
        self.default = default
        self.type = value_type
        self.nargs = nargs
        self.help = help_text
        self.kind = "option" if self.names[0].startswith("-") else "positional"
        self.takes_value = action not in (ACTION_STORE_TRUE, ACTION_HELP)

    @classmethod
    def from_add(cls, names, kw):
        dest = derive_dest(names, kw.get("dest"))
        return cls(
            names=names,
            dest=dest,
            action=kw.get("action", ACTION_STORE),
            default=kw.get("default"),
            value_type=kw.get("type"),
            nargs=kw.get("nargs"),
            help_text=kw.get("help", ""),
        )

    @classmethod
    def help_spec(cls):
        names = ("-h", "--help")
        return cls(
            names=names,
            dest=derive_dest(names, None),
            action=ACTION_HELP,
            default=None,
            value_type=None,
            nargs=None,
            help_text="显示本帮助",
        )


class SpecBook(object):
    """声明表：维护声明顺序、别名查表、位置参数视图。

    别名 -> Spec 的表只在 add() 时增长，parse 不再每次现搭。
    """

    def __init__(self):
        self._specs = [Spec.help_spec()]
        self._options = {}
        for name in self._specs[0].names:
            self._options[name] = self._specs[0]

    def add(self, spec):
        self._specs.append(spec)
        if spec.kind == "option":
            for name in spec.names:
                self._options[name] = spec

    @property
    def specs(self):
        return self._specs

    @property
    def user_options(self):
        """用户声明的选项，保持 add 顺序（不含自动的 -h/--help）。"""
        return [s for s in self._specs
                if s.kind == "option" and s.action != ACTION_HELP]

    @property
    def help_option(self):
        return self._specs[0]

    @property
    def single_positionals(self):
        return [s for s in self._specs
                if s.kind == "positional" and s.nargs != "*"]

    @property
    def star_positional(self):
        for s in self._specs:
            if s.kind == "positional" and s.nargs == "*":
                return s
        return None

    def lookup_option(self, name):
        return self._options.get(name)
