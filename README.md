# addrbook

机房内部用的 IPv4 地址池库，纯标准库，无第三方依赖。

## 现状

包分两层：

- `addrbook/address.py`：地址与网段的算术。地址用 32 位整数表示，
  `parse_addr` / `format_addr` 做点分文本互转，`parse_cidr` / `format_cidr`
  处理 a.b.c.d/len（主机位自动归零），`network_of` / `broadcast_of` /
  `block_size` / `usable_bounds` 提供网段边界计算
- `addrbook/pool.py`：`AddressPool`

`AddressPool(start, end)` 管一段闭区间的连续地址：

- `allocate()` 分配当前最小的空闲地址，池满报 `PoolExhausted`
- `request(addr)` 点名申请某个地址，已占用报 `AddressInUse`
- `release(addr)` 归还地址，没分配过报 `AddressNotAllocated`
- `address` 越界一律报 `OutOfRange`
- `capacity` / `free` / `in_use` / `contains` / `is_allocated` / `allocated()`
  提供只读视图，`allocated()` 返回升序列表

`AddressPool.from_cidr(text, usable_only=True)` 按 CIDR 建池，默认按可用
地址建：/30 及更短扣掉网络地址与广播地址，/31 与 /32 整段可用；传
`usable_only=False` 则整段全收，连网络地址和广播地址都能分配。

## 目标

见任务描述。约束：

- `tests/` 下现有测试一字不改，必须保持全绿
- 纯标准库，不引入三方依赖

## 运行

```bash
python3 demo.py                          # 分配、点名申请与归还演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
