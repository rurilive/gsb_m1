# orset

支持add、remove与contains的基础集合，纯标准库，无外部依赖。

## 现状

orset/set.py提供ORSet：

- 构造时可传入初始元素，元素为字符串
- add(element)加入元素并返回自身，重复加入保持幂等
- remove(element)删除元素并返回自身，元素不在时按无操作处理
- contains(element)返回元素是否在集合里
- elements()返回元素集合的副本，改动副本不影响集合自身
- 非字符串元素在add与remove处抛SetError

## 问题

集合只认本地状态，没有副本标识与版本信息，两个副本各自改动后无法合并；
删除直接抹掉元素，一旦与并发新增相遇就会把对方新加的元素也一起删掉；
既没有幂等交换的合并，也没有因果就绪判断与最终一致保证。

## 目标

见任务描述。约束：

- 现有行为与基线测试一致，基线一个字不改
- 纯标准库

## 运行

python3 demo.py
python3 -m unittest discover -s tests -v