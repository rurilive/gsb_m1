# permorder

排列生成与字典序的朴素求解器，纯标准库，无外部依赖。

## 现状

`permorder/core.py` 提供 `PermOrder`：

- `next_permutation(items)`：下一个字典序排列，靠枚举全部不重复排列排序后取相邻那条，列表入参会被就地改写，到达最大排列时回绕到最小排列
- `kth_permutation(seq, k)`：按字典序排第 k 个的排列，序号从零起算，先枚举全部再按下标取
- `rank(perm)`：一个排列在它所属多重集合全部不重复排列里的名次，从零起算
- `unrank(basis, k)`：按名次反查排列，基准多重集合须以升序给出
- `is_permutation(a, b)`：判断一个序列是不是另一个的排列，两边各自排序后逐位比较

异常基类是 `PermOrderError`，参数不是可比较序列抛 `TypeMismatchError`，序号越界抛
`OutOfRangeError`，反查基准未升序抛 `UnsortedBasisError`。全部路径都靠递归枚举加
排序，结果确定，但元素一多枚举的排列数就按阶乘量级膨胀。

## 问题

没有就地求下一个排列的做法，得先把全部排列枚举排序；第几个排列与按名次反查同样
先枚举全部，元素稍多就在枚举上卡死；含重复元素时既没有不重复口径的就地构造，也没
有康托展开式的名次互转；现有的两条路径之间也缺少逐项一致性与枚举规模的对照。

## 目标

见任务描述。约束：

- `tests/test_core.py` 行为基线保持不变（基线一个字不改，须全绿）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

（实现后补，10 行以内）
