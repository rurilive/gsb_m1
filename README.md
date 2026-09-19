# pluginhost

进程内插件宿主：插件实现 `Plugin` 基类挂到 `PluginHost` 上，宿主按优先级
调度钩子。单进程内嵌，纯标准库。

## 模块结构

- `pluginhost/plugin.py`：`Plugin` 基类。类属性 `name` / `priority`，
  生命周期回调 `on_registered(host)`，业务钩子示例 `on_message`
- `pluginhost/host.py`：`PluginHost` 的注册、排序与 `dispatch`
- `pluginhost/plugins.py`：内置示例插件（audit / mask / signer），demo 使用

## 调用约定

- 注册：`register(plugin)` 要求 `Plugin` 实例（否则 `TypeError`），
  `name` 非空且唯一（否则 `ValueError`）；`on_registered` 抛错则注册
  回滚（插件不留在宿主上）、异常原样上抛
- 顺序：按 `priority` 升序调用，相同 priority 按注册先后
- `dispatch(hook, payload)`：开始时对插件列表取快照，依次调用每个
  插件的同名可调用属性；没有该属性的插件跳过；钩子返回 None 透传
  当前 payload，返回值作为下一个插件的输入，最终返回值即 dispatch 结果
- 注销：`unregister(plugin)` 把插件从调用链摘除，幂等（不在册则
  静默返回），只摘除、不触发任何回调；本轮 dispatch 用快照不受影响，
  下一轮生效；注销后重新注册排在同 priority 末尾
- 错误隔离：钩子抛错只跳过该插件，抛错前的 payload 继续往下游传；
  错误按发生顺序追加进 `host.diagnostics`（`Diagnostic` 记插件名、
  钩子名、原异常），并按 priority 触发所有在册插件的 `on_error(diag)`；
  `on_error` 再抛错只记 diagnostics，不二次触发

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 扩展说明

- `unregister` 与 `dispatch` 的轮次边界：一轮 dispatch 开始时对调用链
  取快照，轮内注册/注销（包括 `on_error` 里的）都不影响本轮，下一轮生效
- `on_error` 遍历同样取快照，轮内增删插件不会改坏正在遍历的链，
  每个在册插件恰好收到一次事件
- 错误事件按触发时的在册名单派发：轮内新注册的插件也能收到
  本轮稍后的 `on_error`
- `host.diagnostics` 只增不减，可直接读取或按需清空
