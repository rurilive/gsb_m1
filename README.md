# routez

前缀路由表，纯标准库，Python 3.10+，无外部依赖。

## 现状

`routez/router.py` 只提供朴素线性匹配，模式一律当字面路径对待：

- `Router.add(path, handler)`：注册一条静态路由，重复注册报错
- `Router.remove(path)`：注销一条路由，未注册则报错
- `Router.match(path)`：按注册顺序逐条逐段全等比较，命中返回
  `Match(handler, params)`，其中 `params` 恒为空字典；未命中返回 `None`
- `Router.routes()`：按注册顺序列出全部路径

路径约定以斜杠开头，根路径为单个斜杠，空段、缺前导斜杠、尾斜杠
一律判为非法并立刻报错。模式里的冒号、星号目前都只是普通字符。

## 问题

线性扫描撑不起一个真正的路由器：段没有建树，查找要逐条比一遍；
冒号参数与星号通配完全没有语义，参数无从提取；同一路径前缀下
没有任何优先级概念，谁先注册谁先命中；注销靠重建列表，路径一多
查找与注销都退化成全表扫描。

## 目标

见任务描述。约束：

- `tests/test_match.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件 `tests/test_router.py`
- 纯标准库，不得引入任何第三方依赖

## 运行

```bash
python3 demo.py                          # 静态匹配演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

（实现后补，10 行以内）