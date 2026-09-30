# pdsu

可持久化并查集，纯标准库，无外部依赖。工程里常要在同一个森林上不断合并，
又想回查任意历史版本的连通性、集合大小与分组，pdsu 就是负责这件事的那一层。

## 现状

pdsu/forest.py 目前是最朴素的一层实现：

- PersistentDSU(n, labels)：建出版本零，每个元素各自成集合
- union(version, a, b)：在某个版本上合并两棵树，返回新版本号
- connected(version, a, b)：判断某版本里两元素是否连通
- size(version, elem)：给出某版本里元素所在集合的成员个数
- members(version, elem) / groups(version) / group_count(version)
- representative(version, elem)、parent_of(version, elem)、version_count()、
  merge_count()
- 全部异常继承 Erro 基类，再分 DsuInputError、UnknownElemError 两个子类

现有实现每次合并都把该版本的整张父指针数组整份拷一份存成新版本，历史版本
逐个查询时按键取出那一整份快照。结果对，但每次合并都要线性拷贝，历史版本一
多内存就平方增长；也还没有一条只改动路径上少数位置、生成新版本根的做法可以
拿来逐项对照。

## 问题

把现有这套整份拷贝扩成路径仅改动、其余复用的做法，缺的东西集中在几处：合并
没有只在路径上改动少数位置并生成新版本根；没有按父指针可持久承载后仍能在近
对数内查任意历史版本某个结点的代表元；也没有另起一条保留全部版本父指针快照
的独立做法做逐项一致对照。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_forest.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+
- 结果确定性，固定输入重复跑新老两条路径逐项一致

## 运行

python3 demo.py
python3 -m unittest discover -s tests

（实现后补，10 行以内）
