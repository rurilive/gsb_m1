# verkit

依赖管理工具里的语义化版本模块，单进程内嵌，纯标准库，无外部依赖。

## 现状

`verkit/version.py` 提供 `parse_version(text)`（解析 semver 2.0.0 字符串，
非法输入抛 `ValueError`，不接受 v 前缀与前导零）与 `compare(a, b)`
（优先级比较，返回 -1/0/1，接受版本对象或字符串）。prerelease 标识符的
优先级规则（数字低于字母数字、更长的标识符组更高、正式版高于一切预发布）
与 build 元数据忽略规则按规范实现。

## 问题

调用方现在只能拿到两两比较的结果。"这个版本落不落在某个版本区间"的判断
散落在各个调用点，prerelease 该不该参与匹配各写各的，口径不一致，
间接依赖的版本约束（`^` / `~` 那套写法）没法直接消费。

## 约定

- `parse_version` / `compare` 的现有行为不变（`tests/test_version.py` 是行为基线，一个字不改）
- 新能力以新增接口提供，不改动现有函数签名
- 纯标准库

## 运行

```bash
python3 demo.py                          # 解析与排序演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

- `parse_range(text)` 按 `||` 切 OR 分支，分支内空格即 AND；`match(version, range)` 任一分支满足即可，`best(versions, range)` 取满足者中优先级最高、无则 `None`。
- `^` 按 npm caret 展开：`^M.m.p` => `>=M.m.p <(M+1).0.0`；`M=0` 时锁 minor（`<0.(m+1).0`），`M=m=0` 时连 patch 也锁（`<0.0.(p+1)`）。
- `~` 按 npm tilde 展开：`>=M.m.p <M.(m+1).0`，只放开 patch。
- 缺省段先补 `.0` 再套用上述展开，如 `~1` == `~1.0.0`、`^1.2` == `^1.2.0`；裸版本（`1.2`、`1`）补零后按精确版本。
- `1.x`/`1.2.x`/`*` 为通配（仅配合 `=`/`^`/`~`/大小比较，`!=` 只接受精确版本）；`!=` 按 semver 优先级精确排除，忽略 build。
- prerelease 默认不匹配任何区间；仅当某 OR（AND）分支内存在与候选同一 `major.minor.patch` 且显式带 prerelease 的比较子时，该候选才被此分支放行。
