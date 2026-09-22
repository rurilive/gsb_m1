# docbase

工单知识库用的本地文档模块，纯标准库，无外部依赖。

## 现状

`docbase/text.py` 管切分：

- `chunks(text)` 把文本切成连续的中文段与其它段，标点空白会把中文段断开
- `tokens(text)` 是当前查询与精确匹配共用的口径，中文按单字、英文数字按段转小写
- `is_cjk(ch)` 判断单字符是否落进中文码位区段

`docbase/library.py` 提供 `DocLibrary`：

- `add(doc_id, text)` 写入，新主键返回 True、覆盖返回 False
- `remove(doc_id)` 删除，删掉返回 True、本来没有返回 False
- `get(doc_id)` 取文本（不存在给 None），`ids()` / `count()` / `scan()` 看全量
- `search(term)` 精确匹配：term 切出的每个 token 都出现在文档里才算命中，
  全量扫描，按主键排序返回；空 term 给空列表
- `stats()` 给篇数，以及累计的 `adds` / `removes` / `searches` / `scanned`
- `subscribe(cb)` / `unsubscribe(cb)`：每次写入、覆盖、删除同步回调
  `(doc_id, old_text, new_text)`，新增时 `old_text` 为 None，删除时 `new_text`
  为 None，对未收录主键的删除不回调

`docbase/rank.py` 提供 `BM25Index`，按相关度出结果：

- `BM25Index(library, k1=1.5, b=0.75)` 构造时收下整个库，之后靠
  `subscribe` 回调增量跟进：增、删、覆盖都会同步维护倒排表、df 与平均
  长度，删掉的主键不会再出现，重插按新文本重算；`close()` 摘掉回调
- `search(query, k)` 按标准 BM25 给前 k 条 `(doc_id, 分数)`，同分按
  doc_id 字典序；空查询、`k <= 0` 或空库都给空列表
- `stats()` 给篇数、词表大小、平均长度，以及累计的 `searches` /
  `candidates` / `scored`

## 实现口径

- 切词：`rank_tokens` 与 `tokens` 不同——中文段切相邻二字组，段里只剩
  一字时保留这个单字；英文数字段照旧切小写词。查询词去重后再打分
- 打分：`score(d) = Σ idf·tf·(k1+1) / (tf + k1·(1-b+b·dl/avgdl))`，
  `idf = ln((N-df+0.5)/(df+0.5) + 1)`，N、df、avgdl 都取查询当时的值
- 剪枝：候选是查询词倒排表的并集；每个词的上界分是 `idf·(k1+1)`（tf
  归一项恒小于 k1+1），按候选上界从高到低精确打分，第 k 名分数一旦
  超过剩余候选的上界就停，命中的文档不会全部打分，`scored` 只记精确
  打分的次数
- 开销：单篇增删只动这篇文档自己的词，不随库规模涨；十万篇、万级词表
  上常见词配生僻词查前二十在一秒内，`scored` 远低于命中数的三成

## 目标

见任务描述。约束：

- 现有行为与 `tests/` 下的基线保持不变（基线一个字不改）
- 纯标准库，运行环境没有网络

## 运行

```bash
python3 demo.py                          # 写入、覆盖、查询与删除演示
python3 -m unittest discover -s tests -v # 行为基线测试
```

`tests/test_rank.py` 是 BM25 的新测试：随机语料混合增删后与暴力打分
对拍名次和分数，另含十万篇的性能用例。
