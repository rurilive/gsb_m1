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

- `BM25Index(library, k1=1.5, b=0.75)` 构造时收下整个库，并挂回调跟随
  后续增删改；`close()` 摘回调
- `search(query, k=10)` 给前 k 条 `(doc_id, 分数)`，分数降序、同分按 id
  字典序；只给至少含一个查询词的文档打分
- `stats()` 给篇数、词表大小、平均词数，以及累计的 `searches` / `scored`
  （实际打分次数）

实现口径：

- 切词用 `rank_tokens`：中文段取相邻二字组，段长为一时保留单字；英文
  数字按段切并转小写；查询词先去重再打分
- 打分是标准 BM25：`idf = ln((N - df + 0.5) / (df + 0.5) + 1)`，词项
  贡献 `idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avgdl))`
- 倒排、文档长度、词频直方图随库的回调逐篇增量维护，N、df、平均长度
  即时跟上，单篇增删开销不随库规模上涨；删除的文档立刻从倒排里摘掉，
  覆盖写按新文本重算
- 查询按 idf 从高到低处理倒排表，用各词项的分数上界（取该词最大词频、
  文档长度取下界）估出未打分文档的总分上限，够不着当前第 k 名就整批
  跳过，名次与分数和全量暴力打分完全一致

## 目标

见任务描述。约束：

- 现有行为与 `tests/` 下的基线保持不变（基线一个字不改）
- 纯标准库，运行环境没有网络

## 运行

```bash
python3 demo.py                          # 写入、覆盖、查询、排序与删除演示
python3 -m unittest discover -s tests -v # 行为基线 + BM25 对拍测试
```
