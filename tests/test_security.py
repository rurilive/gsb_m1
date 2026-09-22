"""安全行为：定点攻击用例，外加随机恶意条目与 SafePlanner 逐条对拍。

对拍口径：同一个归档，Extractor 落盘，SafePlanner 只推演，两边的
action / relpath / reason 必须逐条一致；收完场再扫目标目录，任何
realpath 落到目标目录外都算没修完。
"""

import os
import random
import shutil
import tarfile
import tempfile
import unittest

import support  # noqa: F401  先挂 sys.path

from unseal import KIND_DIR, KIND_FILE, KIND_HARDLINK, KIND_SYMLINK, Extractor
from unseal.entries import iter_archive
from unseal.reference import Forged, SafePlanner, forge_tar, forge_zip


class SecurityCaseTest(unittest.TestCase):
    """审计翻出来的几类现场，逐类钉死。"""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="unseal-sec-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.dest = os.path.join(self.dir, "dest")

    def make_zip(self, items, name="pack.zip"):
        path = os.path.join(self.dir, name)
        forge_zip(path, items)
        return path

    def make_tar(self, items, name="pack.tar"):
        path = os.path.join(self.dir, name)
        forge_tar(path, items)
        return path

    def test_parent_component_rejected(self):
        path = self.make_zip([
            Forged("docs/ok.txt", data=b"ok"),
            Forged("../escaped.txt", data=b"bad"),
            Forged("a/../../escaped2.txt", data=b"bad"),
        ])
        report = Extractor(self.dest).run(path)
        self.assertEqual([item.action for item in report.results],
                         ["write", "reject", "reject"])
        self.assertEqual(report.results[1].reason, "parent-component")
        self.assertFalse(os.path.exists(os.path.join(self.dir, "escaped.txt")))
        # 拒掉的条目不留痕迹，连中间目录也不留
        self.assertEqual(sorted(support.tree(self.dest)),
                         ["docs", "docs/ok.txt"])

    def test_absolute_and_backslash_and_empty_names_rejected(self):
        path = self.make_zip([
            Forged("/tmp/abs.txt", data=b"bad"),
            Forged("..\\win.txt", data=b"bad"),
            Forged("", data=b"bad"),
            Forged("./", kind=KIND_DIR),
        ])
        report = Extractor(self.dest).run(path)
        self.assertEqual([item.reason for item in report.results],
                         ["absolute-name", "backslash-name", "empty-name",
                          "empty-name"])
        self.assertEqual(support.tree(self.dest), {})

    def test_symlink_escape_rejected_then_followup_lands_inside(self):
        outside = os.path.join(self.dir, "outside")
        os.makedirs(outside)
        path = self.make_tar([
            Forged("data/", kind=KIND_DIR),
            Forged("data/out", kind=KIND_SYMLINK, target=outside),
            Forged("data/up", kind=KIND_SYMLINK, target="../../.."),
            Forged("data/out/planted.txt", data=b"planted"),
        ])
        report = Extractor(self.dest).run(path)
        self.assertEqual([item.action for item in report.results],
                         ["mkdir", "reject", "reject", "write"])
        self.assertEqual(report.results[1].reason, "link-escape")
        self.assertEqual(report.results[2].reason, "link-escape")
        # 软链被拒，后续条目落在目标目录里面，外面干净
        self.assertEqual(os.listdir(outside), [])
        self.assertEqual(support.read(self.dest, "data/out/planted.txt"),
                         b"planted")

    def test_inbound_symlink_chain_resolves_inside(self):
        path = self.make_tar([
            Forged("real/", kind=KIND_DIR),
            Forged("real/f.txt", data=b"payload"),
            Forged("alias", kind=KIND_SYMLINK, target="real"),
            Forged("alias/g.txt", data=b"through"),
        ])
        report = Extractor(self.dest).run(path)
        self.assertEqual(report.results[3].action, "write")
        self.assertEqual(report.results[3].relpath, "real/g.txt")
        self.assertEqual(support.read(self.dest, "real/g.txt"), b"through")
        self.assertEqual(support.read(self.dest, "alias/g.txt"), b"through")

    def test_hardlink_rules(self):
        path = self.make_tar([
            Forged("real.txt", data=b"payload"),
            Forged("hard", kind=KIND_HARDLINK, target="real.txt"),
            Forged("ghost", kind=KIND_HARDLINK, target="missing.txt"),
            Forged("escape", kind=KIND_HARDLINK, target="../real.txt"),
            Forged("toadir", kind=KIND_HARDLINK, target="."),
        ])
        report = Extractor(self.dest).run(path)
        self.assertEqual([item.action for item in report.results],
                         ["write", "hardlink", "reject", "reject", "reject"])
        self.assertEqual([item.reason for item in report.results[2:]],
                         ["missing-link-target", "link-escape",
                          "link-escape"])
        self.assertEqual(support.read(self.dest, "hard"), b"payload")

    def test_case_and_unicode_collision_rejected(self):
        path = self.make_zip([
            Forged("Readme.txt", data=b"first"),
            Forged("readme.txt", data=b"second"),
            Forged("café.txt", data=b"nfc"),
            Forged("café.txt", data=b"nfd"),
            Forged("Docs/", kind=KIND_DIR),
            Forged("docs/x.txt", data=b"bad"),
        ])
        report = Extractor(self.dest).run(path)
        self.assertEqual([item.action for item in report.results],
                         ["write", "reject", "write", "reject",
                          "mkdir", "reject"])
        self.assertEqual(report.results[1].reason, "case-collision")
        self.assertEqual(report.results[3].reason, "case-collision")
        self.assertEqual(report.results[5].reason, "case-collision")
        self.assertEqual(support.read(self.dest, "Readme.txt"), b"first")

    def test_conflicting_entries_rejected(self):
        path = self.make_tar([
            Forged("f.txt", data=b"file"),
            Forged("f.txt", kind=KIND_DIR),
            Forged("f.txt/inner.txt", data=b"bad"),
            Forged("d/", kind=KIND_DIR),
            Forged("d", data=b"bad"),
        ])
        report = Extractor(self.dest).run(path)
        self.assertEqual([item.action for item in report.results],
                         ["write", "reject", "reject", "mkdir", "reject"])
        self.assertEqual([item.reason for item in report.results
                          if item.reason is not None],
                         ["conflicting-entry"] * 3)

    def test_oversize_rejected_without_writing(self):
        path = self.make_zip([
            Forged("big.bin", data=b"\0" * 4096, declared=1 << 30),
        ])
        report = Extractor(self.dest, max_entry_bytes=1 << 20).run(path)
        self.assertEqual(report.results[0].action, "reject")
        self.assertEqual(report.results[0].reason, "oversize")
        self.assertEqual(report.bytes, 0)
        self.assertEqual(support.tree(self.dest), {})

    def test_size_mismatch_rejected_without_trace(self):
        path = self.make_zip([
            Forged("short.bin", data=b"abc", declared=100),
            Forged("long.bin", data=b"x" * 100, declared=3),
        ])
        report = Extractor(self.dest).run(path)
        self.assertEqual([item.reason for item in report.results],
                         ["size-mismatch", "size-mismatch"])
        self.assertEqual(report.bytes, 0)
        # 不留半截文件，也不留临时文件
        self.assertEqual(support.tree(self.dest), {})

    def test_half_file_is_rewritten_not_skipped(self):
        payload = b"id,name\n1,alpha\n2,beta\n"
        path = self.make_zip([Forged("report.csv", data=payload)])
        os.makedirs(self.dest)
        support.write(self.dest, "report.csv", payload[:8])
        report = Extractor(self.dest).run(path)
        self.assertEqual(report.results[0].action, "write")
        self.assertEqual(support.read(self.dest, "report.csv"), payload)

    def test_rerun_is_idempotent_for_links_too(self):
        path = self.make_tar([
            Forged("data/", kind=KIND_DIR),
            Forged("data/real.txt", data=b"payload"),
            Forged("data/soft", kind=KIND_SYMLINK, target="real.txt"),
            Forged("data/hard", kind=KIND_HARDLINK, target="data/real.txt"),
        ])
        first = Extractor(self.dest).run(path)
        before = support.tree(self.dest)
        second = Extractor(self.dest).run(path)
        self.assertEqual([item.action for item in first.results],
                         ["mkdir", "write", "symlink", "hardlink"])
        self.assertEqual([item.action for item in second.results],
                         ["mkdir", "skip", "skip", "skip"])
        self.assertEqual(support.tree(self.dest), before)

    def test_unknown_tar_member_rejected(self):
        path = os.path.join(self.dir, "odd.tar")
        with tarfile.open(path, "w") as archive:
            info = tarfile.TarInfo("pipe")
            info.type = tarfile.FIFOTYPE
            archive.addfile(info)
        report = Extractor(self.dest).run(path)
        self.assertEqual(report.results[0].action, "reject")
        self.assertEqual(report.results[0].reason, "unknown-kind")
        self.assertEqual(support.tree(self.dest), {})


_COMPONENTS = ["a", "b", "c", "A", "B", "dir", "DIR", "x.txt", "Y.TXT",
               "café", "café", "..", ".", "", "sp ace", "back\\slash",
               "deep"]
_LINKNAMES = ["a", "b", "dir", "x.txt", ".", "./a", "a/b", "dir/a", "..",
              "../..", "../../etc", "/etc", "/abs/path", "a/../b",
              "b\\ad", "missing/deep"]


def _random_name(rng):
    parts = [rng.choice(_COMPONENTS) for _ in range(rng.randint(1, 4))]
    name = "/".join(parts)
    if rng.random() < 0.1:
        name = "/" + name
    if rng.random() < 0.15:
        name += "/"
    return name


def _random_items(rng, fmt):
    items = []
    kinds = [KIND_FILE] * 5 + [KIND_DIR] * 2 + [KIND_SYMLINK] * 2
    if fmt == "tar":
        kinds.append(KIND_HARDLINK)
    for _ in range(rng.randint(4, 24)):
        kind = rng.choice(kinds)
        name = _random_name(rng)
        if kind == KIND_FILE:
            data = bytes(rng.randrange(256)
                         for _ in range(rng.randint(0, 200)))
            declared = None
            if fmt == "zip" and rng.random() < 0.25:
                declared = rng.choice([0, max(0, len(data) - 1),
                                       len(data) + 1, 1 << 30])
            items.append(Forged(name, KIND_FILE, data=data,
                                declared=declared))
        elif kind == KIND_DIR:
            items.append(Forged(name, KIND_DIR))
        elif kind == KIND_SYMLINK:
            items.append(Forged(name, KIND_SYMLINK,
                                target=rng.choice(_LINKNAMES)))
        else:
            items.append(Forged(name, KIND_HARDLINK,
                                target=rng.choice(_LINKNAMES)))
    return items


def _forge_stable(fmt, path, items, planner_dest):
    """拼归档；盘上落不下的条目（软链环、落点是目标根）剔除后重拼。

    SafePlanner 只推演不落盘，软链自环在它的模型里能停下，但盘上
    realpath 撞环是 ELOOP，这类条目两边没法对齐，对拍前剔掉。
    """
    items = list(items)
    while True:
        if fmt == "zip":
            forge_zip(path, items)
        else:
            forge_tar(path, items)
        verdicts = SafePlanner(planner_dest).plan(list(iter_archive(path)))
        links = {verdict.relpath for verdict in verdicts
                 if verdict.action == "symlink"}
        bad = None
        for index, verdict in enumerate(verdicts):
            if verdict.action == "reject":
                continue
            if verdict.action != "mkdir" and not verdict.relpath:
                bad = index
                break
            parts = verdict.relpath.split("/") if verdict.relpath else []
            if any("/".join(parts[:i]) in links
                   for i in range(1, len(parts))):
                bad = index
                break
        if bad is None:
            return verdicts
        del items[bad]


class FuzzAlignTest(unittest.TestCase):
    """随机恶意条目，两种格式，Extractor 与 SafePlanner 逐条对齐。"""

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="unseal-fuzz-")
        self.addCleanup(shutil.rmtree, self.dir, True)

    def run_trial(self, fmt, seed):
        rng = random.Random(seed)
        tmp = os.path.join(self.dir, "%s-%d" % (fmt, seed))
        os.makedirs(tmp)
        archive = os.path.join(tmp, "pack." + fmt)
        dest = os.path.join(tmp, "dest")
        items = _random_items(rng, fmt)
        verdicts = _forge_stable(fmt, archive, items,
                                 os.path.join(tmp, "nowhere"))
        report = Extractor(dest).run(archive)
        self.assertEqual(len(report.results), len(verdicts))
        for result, verdict in zip(report.results, verdicts):
            self.assertEqual(
                (result.name, result.action, result.relpath, result.reason),
                (verdict.name, verdict.action, verdict.relpath,
                 verdict.reason),
                "条目 %r 判定不一致" % (result.name,))
        self.assert_contained(tmp, archive, dest)

    def assert_contained(self, tmp, archive, dest):
        archive_real = os.path.realpath(archive)
        dest_real = os.path.realpath(dest)
        for base, dirs, files in os.walk(tmp, followlinks=False):
            for name in dirs + files:
                path = os.path.join(base, name)
                real = os.path.realpath(path)
                self.assertTrue(
                    real == archive_real or real == dest_real
                    or real.startswith(dest_real + os.sep),
                    "realpath 越界: %r -> %r" % (path, real))

    def test_fuzz_zip(self):
        for trial in range(25):
            with self.subTest(trial=trial):
                self.run_trial("zip", 20260922 + trial)

    def test_fuzz_tar(self):
        for trial in range(25):
            with self.subTest(trial=trial):
                self.run_trial("tar", 40961023 + trial)


if __name__ == "__main__":
    unittest.main()
