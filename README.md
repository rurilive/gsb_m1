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

`docbase/rank.py` 提供 `BM25Index`，在库上按相关度出结果：

- 构造 `BM25Index(lib, k1=1.5, b=0.75)` 时把库里已有文档收进来建倒排，
  并通过 `subscribe` 跟随后续增删：N、df、平均长度同步更新，删掉的
  文档不再出现，重插按新文本重算；单篇增删只动该文档涉及的倒排表项，
  开销不随库规模涨
- 排序切词走 `rank_tokens`，与 `tokens` 不同：中文段取相邻二字组
  （“支付超时” → 支付 / 付超 / 超时），段只剩一字时保留该字；
  英文数字仍按段切并转小写；查询词先按此口径切再去重
- `search(query, k)` 按标准 BM25 打分取前 k 条 `(doc_id, score)`：
  IDF 取 `ln((N-df+0.5)/(df+0.5)+1)`，同分按主键字典序；空查询、
  未收录的词、非正 k 都给空列表
- top-k 用 WAND 剪枝：按各词历史最大 tf 算贡献上界，只给有机会进
  前 k 的文档打分，结果与全量暴力打分一致；`stats()` 给篇数、词表
  大小与累计的 `searches` / `scored`（打分次数）

## 目标

见任务描述。约束：

- 现有行为与 `tests/` 下的基线保持不变（基线一个字不改）
- 纯标准库，运行环境没有网络

## 运行

```bash
python3 demo.py                          # 写入、覆盖、查询、排序与删除演示
python3 -m unittest discover -s tests -v # 行为基线 + BM25 对拍与性能测试
```
