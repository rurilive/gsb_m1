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

- `BM25Index(library, k1=1.5, b=0.75)` 构造时把库里已有文档收进来，
  并订阅回调跟随后续增删改；删掉的主键立即从索引里消失，重插按新文本重算
- `search(query, k)` 按标准 BM25 给前 k 条 `(doc_id, 分数)`，分数降序、
  同分按 id 字典序；只有至少含一个查询词的文档才是候选
- `stats()` 给篇数、词表大小、平均文档长，以及累计的 `searches` / `scored`
  （打分次数）

## 实现口径

- 切词：排序用自己的口径，不动 `text.tokens`。中文段切相邻二字组
  （`支付超时` -> `支付` `付超` `超时`），段里只剩一个字时保留这个单字；
  英文数字照旧按段切并转小写。查询词先按出现顺序去重再打分
- 公式：`IDF = ln((N - df + 0.5) / (df + 0.5) + 1)`，
  单词贡献 `IDF * tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avgdl))`，
  文档分数是各查询词贡献之和
- 索引：倒排（词 -> `{doc_id: tf}`）加每篇文档的词数；N、df、累计长度随
  单篇增删增量维护，单篇开销只跟这篇文档的词数有关，不随库规模涨
- 打分：不给全部命中评分。先把最生僻的查询词命中的文档全打分垫高门槛，
  其余词走 WAND——按各词上界（`IDF * (k1+1) * tfmax / (tfmax + k1*(1-b))`，
  tfmax 由每词的 tf 直方图维护）累计，够不到当前第 k 名的文档整段跳过，
  `stats()["scored"]` 记录实际打分次数

## 目标

见任务描述。约束：

- 现有行为与 `tests/` 下的基线保持不变（基线一个字不改）
- 纯标准库，运行环境没有网络

## 运行

```bash
python3 demo.py                          # 写入、覆盖、查询与删除演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
