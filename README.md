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
