"""aclib 演示脚本。直接运行应返回码为零。"""

from aclib.dict import BruteDict


def main():
    # 第一段:基线功能现场演示(逐个模式扫描)。
    d = BruteDict()
    for word in ["he", "she", "hers"]:
        d.add(word)

    text = "ushers he she"
    print("patterns:", d.patterns())
    print("text:", text)
    print("counts:", d.count_occurrences(text))
    print("first_match:", d.first_match(text))
    print("matches_in:", d.matches_in(text))

    # TODO: 第二段演示（实现后补）
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
