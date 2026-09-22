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

## 目标

见任务描述。约束：

- 现有行为与 `tests/` 下的基线保持不变（基线一个字不改）
- 纯标准库，运行环境没有网络

## 运行

```bash
python3 demo.py                          # 写入、覆盖、查询与删除演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
