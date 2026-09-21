# replug

本地插件运行时，纯标准库，无外部依赖。宿主从插件目录装载插件模块，
调插件的初始化函数建实例状态，再把请求按名字派给插件处理。

## 用法

```python
from replug import PluginRuntime

runtime = PluginRuntime("/var/lib/app/plugins")
runtime.load_all()                      # 装载目录里全部插件
runtime.plugin_names()                  # 已装载的插件名，排序
runtime.request("greeter", {"who": "运维"})   # 派一条请求，返回 handle 的结果
runtime.version_of("greeter")           # "1.0.0"
runtime.state_of("greeter")             # 插件实例状态（活对象）
runtime.manifest_of("greeter")          # PluginManifest: name / version / description
runtime.reload("greeter")               # 不重启热重载一个插件，接住旧状态
runtime.consistency_report()            # 各插件是否落后于它依赖的插件
```

插件模块协议：目录里每个 `.py` 文件是一个插件。

- `PLUGIN` 字典：`name` 必须等于文件名主体，`version` 形如 `1.2.3`，
  `description` 可选，`requires` 可选（所依赖插件名的字符串列表，宿主按
  依赖顺序初始化；依赖缺失或成环整次装载失败）
- `init(ctx)`：可选。返回插件自己的状态对象；`ctx` 有 `name`、`version`、
  `plugin_dir`、`path`。没定义 init 的插件状态是 `None`
- `handle(state, request)`：必须有。处理一条请求并返回结果，改 `state`
  就是改插件的活状态
- `migrate(old_state)`：可选，热重载时用。新版本定义了它，宿主就把旧状态
  的深拷贝交过去，返回值当新状态；没定义就照带旧状态，`init` 不会在
  reload 时再跑

插件要自包含：宿主给模块起的名字带自己的前缀，插件之间不能靠 `import`
相互引用。下划线开头的文件不当作插件。

## 装载语义

`load_all()` 把目录里全部插件重新读一遍（文件改过就会生效），逐个校验
清单、调 init。全程要么全部成功，要么一个插件都不动，宿主维持装载前的
样子并抛错。装载失败、`init` 抛错、`handle` 抛错分别报
`LoadError`、`InitError`、`PluginError`，请求和查询不存在的插件报
`PluginNotFound`。

`replug/restart.py` 里的 `restart_process(plugin_dir, calls)` 是拿来做
语义对拍的全量重启参考：新起一个宿主装载目录当前内容，把这串请求打完。

## 热重载语义

`reload(name)` 只重读指定插件的源文件：新版本定义了可调用的
`migrate(old_state)` 就迁移状态，否则旧状态原样带过去，其他插件一律不动
（被依赖者换了，依赖方不会自动重载，会出现在 `consistency_report()` 里，
直到它自己也被重载或 `load_all()` 全量刷新）。新版本 `requires` 链上宿主
还没装过的插件会自动从磁盘补齐；文件缺失、清单错误、依赖成环同样作废。

导入、初始化、迁移任一步抛错，整次重载作废：旧模块留在 `sys.modules`、
旧版本继续服务、旧状态一个字节不被改动（迁移拿到的是深拷贝），在途请求
用的是进门时那一版，绝不断、绝不新旧混用。换表是单次原子引用替换。

迁移相关错误报 `MigrateError`（`InitError` 的子类）。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 约束

纯标准库；`tests/` 里的行为与 `PluginRuntime` 的对外接口是基线，改动时
不许破坏。
