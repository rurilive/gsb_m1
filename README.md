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
```

插件模块协议：目录里每个 `.py` 文件是一个插件。

- `PLUGIN` 字典：`name` 必须等于文件名主体，`version` 形如 `1.2.3`，
  `description` 可选，`requires` 可选（依赖的其他插件名列表）
- `init(ctx)`：可选。返回插件自己的状态对象；`ctx` 有 `name`、`version`、
  `plugin_dir`、`path`。没定义 init 的插件状态是 `None`
- `handle(state, request)`：必须有。处理一条请求并返回结果，改 `state`
  就是改插件的活状态
- `migrate(old_state)`：可选，热重载时用。宿主把旧状态的深拷贝交给它，
  返回值成为新版本的状态

插件要自包含：宿主给模块起的名字带自己的前缀，插件之间不能靠 `import`
相互引用。下划线开头的文件不当作插件。

## 装载语义

`load_all()` 把目录里全部插件重新读一遍（文件改过就会生效），逐个校验
清单，再按 `requires` 依赖序调 init（被依赖者先 init；缺依赖、依赖成环
报 `ManifestError`）。全程要么全部成功，要么一个插件都不动，宿主维持
装载前的样子并抛错。

## 热重载

`reload(name)` 不重启宿主，只把一个插件的文件重读、重导并原子换上：

- 新版定义了 `migrate(old_state)` 就把旧状态的深拷贝交给它，返回值当
  新状态；没定义就把旧状态（深拷贝）原样带到新版，`init` 不会再调
- 导入、清单校验、迁移任一步抛错，整次重载作废：旧版本继续服务、旧
  状态一个字节不改。迁移失败、复制旧状态失败报 `MigrateError`
- 切换只在最后一步替换一个引用；所有派发与查询走同一把锁，在途请求
  跑完才换，响应不会新旧混用
- reload 不级联：重载被依赖者不会自动重载依赖方。`consistency_report()`
  返回 `{插件名: [直接相邻的、比它新的插件...]}`，空字典表示全宿主版本
  同代

装载失败、`init` 抛错、`handle` 抛错分别报 `LoadError`、`InitError`、
`PluginError`，迁移失败报 `MigrateError`，请求和查询不存在的插件报
`PluginNotFound`。

`replug/restart.py` 里的 `restart_process(plugin_dir, calls)` 是拿来做
语义对拍的全量重启参考：新起一个宿主装载目录当前内容，把这串请求打完。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 约束

纯标准库；`tests/` 里的行为与 `PluginRuntime` 的对外接口是基线，改动时
不许破坏。
