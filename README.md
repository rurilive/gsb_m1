# stackvm

策略脚本用的内嵌栈式虚拟机：定长编码指令集、汇编/反汇编、三块内存段。
单进程内嵌，纯标准库，无外部依赖。

## 模块结构

- `stackvm/opcodes.py`：opcode 编码表（名称 -> 操作码 + 操作数布局），decode 与 disasm 全部由这张表驱动；新增指令只需在表里占一个空闲操作码，并配一个 `_op_<小写名称>` 处理器
- `stackvm/asm.py`：`assemble`（文本 -> 字节码，支持 `标签:`、`#` 注释，自动跳过 disasm 的偏移列）与 `disasm`（字节码 -> 带偏移列的文本）
- `stackvm/vm.py`：VM 执行核心，`_decode` 按表解码出 `(助记符, 操作数, 下一条偏移)`，`_dispatch` 按表分发；跳转类指令在处理器里改写 `self._pc`
- `stackvm/errors.py`：VmError 及其子类（汇编、解码、执行共用）

## 指令与编码

定长编码：1 字节操作码，带操作数的指令后跟 2 字节无符号小端整数
（立即数、跳转偏移或槽位号，一律 0~65535）。当前操作码占用 0x10-0x18
与 0x20-0x29。

| 段 | 说明 |
| --- | --- |
| 全局段 | 构造 VM 时定长，跨 run 保留，LOAD_G / STORE_G 按槽位存取 |
| 操作数栈 | 指令间传值，run 开始时清空 |
| 局部段 | LOAD_LOCAL / STORE_LOCAL 按编号存取，run 开始时清空；CALL 压入全新局部段、RET 恢复调用者局部段，读未初始化编号抛 VmError |

比较指令（EQ/LT/GT）压入布尔值；JZ 弹栈，值为假（False/0）时跳转。
程序必须以 HALT 结尾，跑出末尾或步数超过 `max_steps` 抛 VmError。

## 运行

```bash
python3 demo.py                          # 汇编、反汇编与执行演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

`tests/test_vm.py` 是现有行为的锁定基线。

## 扩展说明

- `CALL addr`：压入调用帧（返回地址 = 下条指令偏移，局部段全新隔离），再跳到 `addr`；`RET`：弹帧并回到返回地址
- 主程序段直接执行 `RET` 抛 `VmError`；操作码 `CALL=0x28(u16)`、`RET=0x29`，汇编/反汇编随编码表自动生效
- 调用深度（不含主程序帧）由 `VM(max_calls=64)` 限定，超限抛 `stackvm.errors.CallOverflow`（`VmError` 子类）
- `tests/test_call.py` 锁定嵌套调用、局部段隔离、深度边界与 RET 落点；`demo.py` 末尾演示递归 fib 与超限报错
