# bloomchain

埋点管线的判重层，纯标准库，无外部依赖。管道在入库前问一句这个键是不是
可能重复，不重复才往下走，避免同一个键被反复处理。

## 现状

- `bloomchain/hashing.py`：哈希原语与参数换算。`digest()` 是加固定盐的
  sha256，`hash_pair()` 劈出两个 64 位无符号数（可选盐区分不同层的展开），
  `bit_indexes()` 做双重哈希展开，`optimal_params()` 按期望元素数与目标
  误判率算位数与哈希次数，`estimate_cardinality()` 用线性计数法估个数。
- `bloomchain/randomstate.py`：`RandomState(seed)` 定种随机流，`salt()` 取
  非零 64 位盐，`below()` 取范围内整数，`fork()` 派生子流。
- `bloomchain/naive.py`：`NaiveBloomFilter(capacity, fp_rate)`，一层定长位
  数组。`add(key)` 置位，`key in bf` 查询，`stats()` 出计数快照。
- `bloomchain/errors.py`：`BloomError` 与 `CapacityError`。

位数组只置位不清位，所以只加不删；一层大小在构造时定死，装满了再没有
弹性；也没有可落盘的格式和可查询的基数估计。

## 问题

单层定长在键量涨起来后要么超载、要么整段重建，容量没有弹性；判重只有
命中查询，拿不到已插入规模的估计，也存不下、读不回、合不了。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
