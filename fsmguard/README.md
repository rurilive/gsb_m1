
## 测试报告

`tests/test_machine.py`（标准库 unittest，仓库根目录运行
`python3 -m unittest discover -s tests -v`）共 22 条用例：18 绿 4 红，
红色用例逐一对应源码与本 README 的出入：

- `test_most_specific_transition_wins`（红）：`_pick` 按 source 路径段数
  升序排序取第一条，最宽泛者优先，违反「最具体者优先」；建议改为按段数
  降序取候选（如 `cands.sort(key=lambda p: -p[0])` 或 `max`）。
- `test_fallback_ignored_when_candidate_exists`（红）：`fire` 中
  `self._fallbacks.get(event) or self._pick(event)` 让默认转移抢在候选
  前面，违反「存在候选时默认转移不参与选择」；建议先 `_pick`，无候选时
  再查 `_fallbacks`。
- `test_guard_exception_propagates_and_state_unchanged`（红）：`fire` 用
  try/except 吞掉守卫异常并按放行处理，违反「守卫异常原样传播、状态不
  变」；建议删除该 try/except，让异常自然向上传播。
- `test_entry_action_exception_rolls_back`（红）：entry 动作在修改状态、
  写入 history 之后才执行，其抛异常时转移未回滚，违反原子性约定；建议
  先执行 exit/entry 动作，全部成功后再更新状态并写 history（或捕获异常
  后回滚状态与 history 再重新抛出）。

修复以上四处后本测试套件应全绿；`python3 demo.py` 行为不受影响。
