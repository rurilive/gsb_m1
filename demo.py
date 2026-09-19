"""diffkit 现状演示：生成补丁、应用、回滚的完整链路。"""

from diffkit import apply_patch, unapply_patch, unified_diff


def section(title):
    print(f"=== {title} ===")


def main():
    # 1) 大段重复行的配置上打补丁
    old_text = "head\n" + "rate 100\n" * 10 + "tail\n"
    lines = ["head"] + ["rate 100"] * 10 + ["tail"]
    lines[5] = "rate 50"
    new_text = "\n".join(lines) + "\n"
    patch = unified_diff(old_text, new_text,
                         fromfile="a/limits.conf", tofile="b/limits.conf")
    section("生成补丁并应用（重复行文件）")
    print(patch, end="")
    applied = apply_patch(old_text, patch)
    print("\n补丁目标内容：")
    print(new_text, end="")
    print("实际应用后：")
    print(applied, end="")
    print()

    # 2) 文件尾字节
    section("文件尾字节")
    print(repr(applied[-16:]))
    print()

    # 3) 补丁基线与目标版本不一致
    section("补丁基线与目标不一致")
    base = "\n".join(f"entry-{i} = ok" for i in range(1, 13)) + "\n"
    patched = base.replace("entry-2 = ok", "entry-2 = changed")
    patched = patched.replace("entry-11 = ok", "entry-11 = changed")
    p2 = unified_diff(base, patched)
    drifted = base.replace("entry-11 = ok", "entry-11 = edited")
    result = apply_patch(drifted, p2)
    print("apply 正常返回，未抛异常")
    print("entry-2 是否更新:", "entry-2 = changed" in result)
    print("entry-11 是否更新:", "entry-11 = changed" in result)
    print()

    # 4) 回滚
    section("反向应用（回滚）")
    old3 = "alpha\nbeta\n"
    new3 = "alpha\nbeta\ngamma\n"
    p3 = unified_diff(old3, new3)
    try:
        restored = unapply_patch(new3, p3)
        print("回滚成功:", repr(restored))
    except ValueError as e:
        print("回滚失败:", e)


if __name__ == "__main__":
    main()
