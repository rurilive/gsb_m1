# fsmguard

任务调度器用的进程内状态机：事件驱动转移，转移可带守卫函数，状态进入/退出
可挂动作。状态名支持点分层级——`busy.compile` 是 `busy` 的子状态，注册在
父状态上的转移对它的所有子状态生效。纯标准库，单线程驱动（调用方自行保证
并发安全）。

## 语义约定（以下为本模块的正式行为定义）

1. **fire(event) -> bool**
   - 接受并完成一次转移返回 True
   - 被守卫拒绝、或当前状态没有该事件的转移 → 返回 False，状态不变，
     不视为错误
2. **转移选择**
   - 候选为所有 source 匹配当前状态的转移：当前状态等于 source，或位于
     source 之下（状态 `busy.compile` 匹配 source `busy`）
   - 多条候选时**最具体者优先**：source 路径段数多者优先，即 `busy.compile`
     上的转移先于 `busy` 上的转移被采用
3. **默认转移 add_fallback(event, target)**
   - 仅当该事件在当前状态**没有任何候选转移**时使用
   - 存在候选时，默认转移不参与选择
4. **守卫 guard(machine)**
   - 返回真值放行；返回假值拒绝（状态不变，fire 返回 False）
   - **guard 抛出的异常必须原样向 fire 调用方传播，状态不得变化**；
     不允许把守卫异常当作放行或拒绝处理
5. **entry/exit 动作与原子性**
   - 转移被接受后依次执行：源状态 exit 动作、目标状态 entry 动作
   - **entry/exit 动作抛异常时，异常向 fire 调用方原样传播；此时状态必须
     保持转移前的状态，且该次转移不得写入 history**（转移要么完整发生，
     要么不发生）
6. **history**
   - 只记录实际完成的转移：`{"event", "from", "to"}`，追加顺序即完成顺序；
     默认转移触发时 from 记为 `"*"`
   - 被拒绝、无匹配、或动作抛异常的尝试一律不记录

`can(event)` 只判断当前状态是否存在该事件的候选转移，不做守卫判断。

## 运行

```bash
python3 demo.py
```

## 测试报告

测试文件：`tests/test_machine.py`（标准库 unittest，共 24 个用例）。

```bash
python3 -m unittest tests.test_machine -v
```

当前结果：**19 绿 5 红**，5 个红用例钉出 4 处源码与本 README 的出入。

| 红用例 | 对应缺陷 | 建议修复方向（一句话） |
| --- | --- | --- |
| `TestTransitionSelection.test_child_transition_takes_precedence_over_parent` | `Machine._pick` 按 depth 升序取第一个，父（浅）转移盖过子（深）转移，与「最具体者优先」相反。 | 改为 depth 降序（或取最大 depth）选候选。 |
| `TestGuards.test_guard_exception_propagates_and_state_unchanged` | `fire` 用 `try/except` 吞掉守卫异常并按放行处理，异常未传播且状态被改变。 | 移除守卫调用的异常捕获，让异常原样传播（守卫在任何状态变更前执行，天然无需回滚）。 |
| `TestFallback.test_fallback_ignored_when_candidate_exists` | `fire` 中 `self._fallbacks.get(event) or self._pick(event)` 使默认转移无条件优先于候选转移。 | 先 `_pick` 候选，候选为 None 时才回退到 `_fallbacks`。 |
| `TestFallback.test_fallback_not_used_when_guard_rejects_candidate` | 同上根因：候选被守卫拒绝时仍走了默认转移（守卫甚至未被求值）。 | 同上：候选优先，存在候选时默认转移不参与选择。 |
| `TestEntryExitActions.test_entry_action_exception_rolls_back` | entry 动作执行前已切换 `_state` 并写入 `history`，entry 抛异常后状态停在目标态、history 残留半完成转移。 | 先跑完 exit/entry 动作再提交状态与 history，或用 try/except 在异常时恢复旧状态并移除该次 history 记录。 |

补充说明：

- 异常用例均断言了异常类型（自定义 `GuardBoom`/`ActionBoom` 经 `assertRaises` 验证原样传播）与状态回滚（状态不变、`history` 不记录、exit 已执行时 entry 不再执行）。
- `exit` 动作抛异常的场景当前行为正确（异常传播、状态未切换、无 history），已有绿用例锁定。
- README 未约定的自由行为（如同深度同事件多候选的先后、同级多动作顺序、`can` 是否感知默认转移等）未强行钉红。
- `fsmguard/` 源码与 `demo.py` 未做任何改动，`python3 demo.py` 照常跑通。
