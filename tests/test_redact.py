import copy
import random
import time
import unittest

from logpipe import (
    LogPipeline,
    MemorySink,
    PathError,
    Redactor,
    RuleError,
    apply_mask,
    format_pattern,
    loads,
    parse_pattern,
)


def sample_record():
    return {
        "ts": "2026-09-21T09:00:00Z",
        "user": {"id": 7, "phone": "13812345678", "city": "北京"},
        "payments": [
            {"card": "6222020200112233", "amount": 12.5, "currency": "CNY"},
            {"card": "6222020200114455", "amount": 3, "currency": "CNY"},
        ],
        "tags": [],
    }


class MaskTests(unittest.TestCase):
    def test_phone_keeps_three_and_four(self):
        self.assertEqual(apply_mask("phone", "13812345678"), "138****5678")

    def test_card_keeps_last_four(self):
        self.assertEqual(
            apply_mask("card", "6222020200112233"), "************2233"
        )

    def test_unknown_mask_stars_all(self):
        self.assertEqual(apply_mask("secret", "abcdef"), "******")

    def test_short_values_star_entirely(self):
        # 11 == head + tail for phone; nothing can be kept.
        self.assertEqual(apply_mask("phone", "1234567"), "*******")
        self.assertEqual(apply_mask("phone", "123"), "***")
        self.assertEqual(apply_mask("card", "1234"), "****")
        self.assertEqual(apply_mask("card", "12"), "**")
        self.assertEqual(apply_mask("card", ""), "")

    def test_length_is_preserved(self):
        for text in ["", "a", "13812345678", "x" * 100]:
            for mask in ("phone", "card", "other"):
                self.assertEqual(len(apply_mask(mask, text)), len(text))

    def test_non_string_scalars_are_coerced_and_typed_as_str(self):
        redactor = Redactor([{"path": "n", "mask": "card"}])
        out = redactor.redact({"n": 1234567890})
        self.assertEqual(out["n"], "******7890")
        self.assertIsInstance(out["n"], str)
        explanation = redactor.explain({"n": 1234567890}, path="n")["leaf"]
        self.assertTrue(explanation["coerced"])
        self.assertEqual(explanation["length"], 10)


class PatternTests(unittest.TestCase):
    def test_literal_segments(self):
        self.assertEqual(
            parse_pattern("user.phone"),
            [("key", "user"), ("key", "phone")],
        )

    def test_wildcard_segments(self):
        self.assertEqual(
            parse_pattern("payments[?].card"),
            [
                ("key", "payments"),
                ("wildcard", "?"),
                ("key", "card"),
            ],
        )
        self.assertEqual(
            parse_pattern("grid[?][?]"),
            [
                ("key", "grid"),
                ("wildcard", "?"),
                ("wildcard", "?"),
            ],
        )

    def test_literal_and_wildcard_indices_distinct(self):
        self.assertEqual(parse_pattern("a[0]")[1], ("index", 0))
        self.assertEqual(parse_pattern("a[?]")[1], ("wildcard", "?"))

    def test_format_round_trip(self):
        for path in ["user.phone", "payments[?].card", "grid[1][?]", "a[0].b"]:
            self.assertEqual(format_pattern(parse_pattern(path)), path)

    def test_bad_patterns(self):
        for path in ["", "a.", ".a", "a[*]", "a[]", "a[-1]", "a[?]b", "a]b"]:
            with self.subTest(path=path):
                with self.assertRaises(PathError):
                    parse_pattern(path)

    def test_bad_rules(self):
        bad_rules = [
            [],  # iterable check happens per item, this is fine
        ]
        del bad_rules
        for rules in (
            [{"mask": "phone"}],
            [{"path": "a"}],
            [{"path": "a", "mask": ""}],
            [{"path": "a", "mask": 3}],
            ["not-a-dict"],
            "not-iterable",
        ):
            with self.subTest(rules=rules):
                with self.assertRaises((RuleError, PathError)):
                    Redactor(rules)


class RedactTests(unittest.TestCase):
    def setUp(self):
        self.redactor = Redactor([
            {"path": "user.phone", "mask": "phone"},
            {"path": "payments[?].card", "mask": "card"},
        ])

    def test_basic_redaction(self):
        out = self.redactor.redact(sample_record())
        self.assertEqual(out["user"]["phone"], "138****5678")
        self.assertEqual(out["payments"][0]["card"], "************2233")
        self.assertEqual(out["payments"][1]["card"], "************4455")
        self.assertEqual(out["user"]["id"], 7)
        self.assertEqual(out["user"]["city"], "北京")
        self.assertEqual(out["payments"][0]["amount"], 12.5)

    def test_input_record_is_not_mutated(self):
        record = sample_record()
        snapshot = copy.deepcopy(record)
        self.redactor.redact(record)
        self.assertEqual(record, snapshot)

    def test_result_shares_no_container_with_input(self):
        record = sample_record()
        out = self.redactor.redact(record)
        self.assertIsNot(out, record)
        self.assertIsNot(out["user"], record["user"])
        self.assertIsNot(out["payments"], record["payments"])

    def test_wildcard_matches_every_item(self):
        record = {"items": [{"card": "1111222233334444"} for _ in range(5)]}
        out = Redactor([{"path": "items[?].card", "mask": "card"}]).redact(record)
        self.assertTrue(
            all(item["card"] == "************4444" for item in out["items"])
        )

    def test_concrete_path_beats_wildcard(self):
        redactor = Redactor([
            {"path": "payments[?].card", "mask": "card"},
            {"path": "payments[0].card", "mask": "phone"},
        ])
        out = redactor.redact(sample_record())
        self.assertEqual(out["payments"][0]["card"], "622*********2233")
        self.assertEqual(out["payments"][1]["card"], "************4455")

    def test_loading_order_wins_at_same_specificity(self):
        redactor = Redactor([
            {"path": "user.phone", "mask": "card"},
            {"path": "user.phone", "mask": "phone"},
        ])
        out = redactor.redact(sample_record())
        self.assertEqual(out["user"]["phone"], "138****5678")

    def test_wildcard_count_is_whole_path_specificity(self):
        record = {"rows": [{"cells": [{"v": "13812345678"}]}]}
        redactor = Redactor([
            {"path": "rows[?].cells[?].v", "mask": "card"},
            {"path": "rows[0].cells[?].v", "mask": "phone"},
        ])
        out = redactor.redact(record)
        self.assertEqual(
            out["rows"][0]["cells"][0]["v"], "138****5678"
        )

    def test_container_endpoints_are_not_masked(self):
        record = {"user": {"phone": "13812345678"}}
        redactor = Redactor([{"path": "user", "mask": "all"}])
        out = redactor.redact(record)
        self.assertEqual(out, record)


class HotReloadTests(unittest.TestCase):
    def test_reload_replaces_all_rules(self):
        redactor = Redactor([{"path": "user.phone", "mask": "phone"}])
        record = sample_record()
        self.assertEqual(
            redactor.redact(record)["user"]["phone"], "138****5678"
        )
        redactor.load_rules([{"path": "payments[?].card", "mask": "card"}])
        out = redactor.redact(record)
        self.assertEqual(out["user"]["phone"], "13812345678")
        self.assertEqual(out["payments"][0]["card"], "************2233")

    def test_reload_to_empty_clears_everything(self):
        redactor = Redactor([{"path": "user.phone", "mask": "phone"}])
        redactor.load_rules([])
        record = sample_record()
        out = redactor.redact(record)
        self.assertEqual(out, record)
        self.assertIsNot(out, record)

    def test_version_counts_reloads(self):
        redactor = Redactor()
        self.assertEqual(redactor.version, 0)
        redactor.load_rules([])
        redactor.load_rules([])
        self.assertEqual(redactor.version, 2)

    def test_failed_reload_keeps_old_rules(self):
        redactor = Redactor([{"path": "user.phone", "mask": "phone"}])
        with self.assertRaises((RuleError, PathError)):
            redactor.load_rules([{"path": "user.phone", "mask": "phone"},
                                 {"path": "bad[", "mask": "card"}])
        self.assertEqual(
            redactor.redact(sample_record())["user"]["phone"], "138****5678"
        )


class BypassPipelineTests(unittest.TestCase):
    def test_no_redactor_means_passthrough(self):
        sink = MemorySink()
        pipeline = LogPipeline(sink)
        record = sample_record()
        line = pipeline.emit(record)
        self.assertEqual(loads(line), record)

    def test_set_redactor_takes_effect_immediately(self):
        sink = MemorySink()
        pipeline = LogPipeline(sink)
        redactor = Redactor([{"path": "user.phone", "mask": "phone"}])
        self.assertIs(pipeline.set_redactor(redactor), redactor)
        line = pipeline.emit(sample_record())
        self.assertEqual(loads(line)["user"]["phone"], "138****5678")

    def test_detaching_redactor_restores_passthrough(self):
        sink = MemorySink()
        pipeline = LogPipeline(sink)
        redactor = Redactor([{"path": "user.phone", "mask": "phone"}])
        pipeline.set_redactor(redactor)
        pipeline.emit(sample_record())
        pipeline.set_redactor(None)
        line = pipeline.emit(sample_record())
        self.assertEqual(loads(line)["user"]["phone"], "13812345678")

    def test_bad_redactor_is_rejected(self):
        pipeline = LogPipeline(MemorySink())
        with self.assertRaises(TypeError):
            pipeline.set_redactor(object())

    def test_original_does_not_land_without_bypass_rule(self):
        sink, bypass = MemorySink(), MemorySink()
        pipeline = LogPipeline(sink)
        pipeline.set_redactor(Redactor(
            [{"path": "user.phone", "mask": "phone"}]
        ))
        pipeline.set_bypass_sink(bypass)
        pipeline.emit(sample_record())
        self.assertEqual(bypass.lines, [])


class EmptyAndOutOfRangeSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.redactor = Redactor([
            {"path": "tags[?]", "mask": "all"},
            {"path": "payments[?].card", "mask": "card"},
            {"path": "payments[3].card", "mask": "card"},
            {"path": "grid[?][?]", "mask": "all"},
        ])

    def test_wildcard_over_empty_array_matches_nothing(self):
        record = {"tags": [], "payments": [], "grid": []}
        self.assertEqual(self.redactor.redact(record), record)

    def test_wildcard_out_of_range_does_not_crash_or_leak(self):
        record = {"payments": [{"card": "6222020200112233"}]}
        out = self.redactor.redact(record)
        self.assertEqual(out["payments"][0]["card"], "************2233")

    def test_explain_pins_empty_array_reason(self):
        rules = {
            item["path"]: item
            for item in self.redactor.explain({"tags": []})["rules"]
        }
        self.assertEqual(rules["tags[?]"]["status"], "no-match")
        self.assertIn("empty", rules["tags[?]"]["reason"])

    def test_explain_pins_concrete_index_out_of_range(self):
        rules = {
            item["path"]: item
            for item in self.redactor.explain(sample_record())["rules"]
        }
        entry = rules["payments[3].card"]
        self.assertEqual(entry["status"], "no-match")
        self.assertEqual(entry["matched_leaves"], 0)
        self.assertIn("out of range", entry["reason"])
        self.assertIn("2 item(s)", entry["reason"])

    def test_explain_pins_wrong_container(self):
        redactor = Redactor([{"path": "a[0]", "mask": "all"}])
        entry = redactor.explain({"a": {"0": "x"}})["rules"][0]
        self.assertEqual(entry["status"], "no-match")
        self.assertIn("expects a list", entry["reason"])

    def test_explain_pins_missing_key(self):
        redactor = Redactor([{"path": "user.email", "mask": "all"}])
        entry = redactor.explain(sample_record())["rules"][0]
        self.assertEqual(entry["status"], "no-match")
        self.assertIn("not found", entry["reason"])

    def test_partial_wildcard_match_reports_missed_branch(self):
        record = {"rows": [{"v": "secret"}, {}, {"v": "secret"}]}
        redactor = Redactor([{"path": "rows[?].v", "mask": "all"}])
        entry = redactor.explain(record)["rules"][0]
        self.assertEqual(entry["status"], "applied")
        self.assertEqual(entry["matched_leaves"], 2)
        self.assertEqual(entry["missed_branches"], 1)


class ExplainTests(unittest.TestCase):
    def setUp(self):
        self.redactor = Redactor([
            {"path": "user.phone", "mask": "phone"},
            {"path": "payments[?].card", "mask": "card"},
            {"path": "user", "mask": "all"},
        ])

    def test_leaves_follow_walk_order(self):
        paths = [
            leaf["path"]
            for leaf in self.redactor.explain(sample_record())["leaves"]
        ]
        self.assertEqual(paths, [
            "ts",
            "user.id",
            "user.phone",
            "user.city",
            "payments[0].card",
            "payments[0].amount",
            "payments[0].currency",
            "payments[1].card",
            "payments[1].amount",
            "payments[1].currency",
        ])

    def test_redacted_leaf_explains_rule(self):
        leaf = self.redactor.explain(sample_record(), path="user.phone")["leaf"]
        self.assertTrue(leaf["redacted"])
        self.assertEqual(leaf["rule"], "user.phone")
        self.assertEqual(leaf["mask"], "phone")
        self.assertFalse(leaf["coerced"])

    def test_untouched_leaf_explains_why(self):
        leaf = self.redactor.explain(sample_record(), path="ts")["leaf"]
        self.assertFalse(leaf["redacted"])
        self.assertEqual(leaf["reason"], "no matching rule")

    def test_rule_statuses(self):
        by_path = {
            item["path"]: item
            for item in self.redactor.explain(sample_record())["rules"]
        }
        self.assertEqual(by_path["user.phone"]["status"], "applied")
        wildcard = by_path["payments[?].card"]
        self.assertEqual(wildcard["status"], "applied")
        self.assertEqual(wildcard["matched_leaves"], 2)
        self.assertEqual(by_path["user"]["status"], "no-match")
        self.assertEqual(by_path["user"]["matched_containers"], 1)

    def test_shadowed_rule_is_explained(self):
        redactor = Redactor([
            {"path": "payments[?].card", "mask": "card"},
            {"path": "payments[0].card", "mask": "phone"},
            {"path": "payments[1].card", "mask": "phone"},
        ])
        by_path = {
            item["path"]: item
            for item in redactor.explain(sample_record())["rules"]
        }
        self.assertEqual(by_path["payments[0].card"]["status"], "applied")
        self.assertEqual(by_path["payments[1].card"]["status"], "applied")
        self.assertEqual(by_path["payments[?].card"]["status"], "shadowed")

    def test_explain_does_not_include_raw_values(self):
        text = repr(self.redactor.explain(sample_record()))
        self.assertNotIn("13812345678", text)
        self.assertNotIn("6222020200112233", text)

    def test_explain_path_to_non_leaf_raises(self):
        with self.assertRaises(PathError):
            self.redactor.explain(sample_record(), path="user")


class DeepNestingAndCycleTests(unittest.TestCase):
    DEPTH = 10000

    def _deep_record(self):
        root = {"secret": "13812345678"}
        current = root
        for _ in range(self.DEPTH):
            child = {"secret": "13812345678"}
            current["child"] = child
            current = child
        return root

    def test_very_deep_nesting_does_not_crash(self):
        root = self._deep_record()
        # A wildcard keeps the trie prefix alive at every depth, while
        # the long concrete path exercises the single-prefix chain.
        deep_path = "child." * self.DEPTH + "secret"
        redactor = Redactor([
            {"path": deep_path, "mask": "phone"},
            {"path": "deep[?].secret", "mask": "phone"},
        ])
        out = redactor.redact(root)
        node = out
        for _ in range(self.DEPTH):
            self.assertEqual(node["secret"], "13812345678")
            node = node["child"]
        self.assertEqual(node["secret"], "138****5678")

    def test_deep_explain_does_not_crash(self):
        root = self._deep_record()
        deep_path = "child." * self.DEPTH + "secret"
        redactor = Redactor([
            {"path": deep_path, "mask": "phone"},
            {"path": "deep[?].secret", "mask": "phone"},
        ])
        leaves = redactor.explain(root)["leaves"]
        self.assertEqual(len(leaves), self.DEPTH + 1)
        self.assertFalse(any(leaf["redacted"] for leaf in leaves[:-1]))
        self.assertTrue(leaves[-1]["redacted"])

    def test_self_cycle_is_closed_and_redacted(self):
        record = {"secret": "13812345678"}
        record["self"] = record
        redactor = Redactor([
            {"path": "secret", "mask": "phone"},
            {"path": "self.secret", "mask": "phone"},
        ])
        out = redactor.redact(record)
        self.assertIs(out["self"], out)
        self.assertEqual(out["secret"], "138****5678")

    def test_list_cycle_is_closed_and_redacted(self):
        record = {"secret": "13812345678"}
        record["items"] = [record]
        redactor = Redactor([
            {"path": "secret", "mask": "phone"},
            {"path": "items[?].secret", "mask": "card"},
        ])
        out = redactor.redact(record)
        self.assertIs(out["items"][0], out)
        self.assertEqual(out["secret"], "138****5678")

    def test_shared_subobject_is_shared_and_masked(self):
        shared = {"card": "6222020200112233"}
        record = {"a": shared, "b": shared}
        redactor = Redactor([
            {"path": "a.card", "mask": "card"},
            {"path": "b.card", "mask": "card"},
        ])
        out = redactor.redact(record)
        self.assertIs(out["a"], out["b"])
        self.assertEqual(out["a"]["card"], "************2233")


def naive_mask(mask, value):
    text = value if isinstance(value, str) else _naive_text(value)
    if mask == "phone":
        if len(text) <= 7:
            return "*" * len(text)
        return text[:3] + "*" * (len(text) - 7) + text[-4:]
    if mask == "card":
        if len(text) <= 4:
            return "*" * len(text)
        return "*" * (len(text) - 4) + text[-4:]
    return "*" * len(text)


def _naive_text(value):
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def naive_pattern_match(rule_segments, leaf_segments):
    if len(rule_segments) != len(leaf_segments):
        return False
    for (kind, value), (leaf_kind, leaf_value) in zip(
        rule_segments, leaf_segments
    ):
        if kind == "wildcard":
            if leaf_kind != "index":
                return False
        elif (kind, value) != (leaf_kind, leaf_value):
            return False
    return True


class NaiveRedactor:
    """Straightforward O(leaves * rules) reference implementation."""

    def __init__(self, rules):
        self.rules = []
        for order, rule in enumerate(rules):
            segments = parse_pattern(rule["path"])
            self.rules.append({
                "segments": segments,
                "wildcards": sum(
                    1 for kind, _ in segments if kind == "wildcard"
                ),
                "order": order,
                "mask": rule["mask"],
            })

    def _winner(self, leaf_segments):
        winner = None
        for rule in self.rules:
            if not naive_pattern_match(rule["segments"], leaf_segments):
                continue
            if winner is None:
                winner = rule
            elif rule["wildcards"] < winner["wildcards"]:
                winner = rule
            elif (
                rule["wildcards"] == winner["wildcards"]
                and rule["order"] > winner["order"]
            ):
                winner = rule
        return winner

    def redact(self, value, segments=()):
        if isinstance(value, dict):
            return {
                key: self.redact(child, segments + (("key", key),))
                for key, child in value.items()
            }
        if isinstance(value, list):
            return [
                self.redact(child, segments + (("index", index),))
                for index, child in enumerate(value)
            ]
        rule = self._winner(segments)
        if rule is None:
            return value
        return naive_mask(rule["mask"], value)


def random_record(rng, depth=0):
    if depth >= 4:
        return rng.choice(["13812345678", "6222020200112233", 42, "x", None])
    kind = rng.random()
    if kind < 0.45:
        return {
            "k%d" % i: random_record(rng, depth + 1)
            for i in range(rng.randrange(4))
        }
    if kind < 0.75:
        return [random_record(rng, depth + 1) for _ in range(rng.randrange(4))]
    return rng.choice(
        ["13812345678", "6222020200112233", "secret", 7, 3.5, True, None]
    )


def leaf_segments_of(value, segments=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from leaf_segments_of(child, segments + (("key", key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from leaf_segments_of(child, segments + (("index", index),))
    else:
        yield segments


def random_rules(rng, record):
    paths = list(leaf_segments_of(record))
    rules = []
    if paths:
        # Rules address at least one container step from the root.
        eligible = [segments for segments in paths if len(segments) > 1]
        if not eligible:
            return rules
        chosen = rng.sample(eligible, k=min(len(eligible), rng.randrange(1, 6)))
        for segments in chosen:
            mutated = []
            for kind, value in segments:
                if kind == "index" and rng.random() < 0.6:
                    mutated.append(("wildcard", "?"))
                else:
                    mutated.append((kind, value))
            rules.append({
                "path": format_pattern(mutated),
                "mask": rng.choice(["phone", "card", "all", "secret"]),
            })
    # Duplicate exact path exercises later-rule-wins.
    if paths and rng.random() < 0.4:
        rules.append({
            "path": format_pattern(paths[0]),
            "mask": rng.choice(["phone", "card", "all"]),
        })
    # Deliberately absent paths: missing keys and out-of-range indices.
    if rng.random() < 0.5:
        rules.append({"path": "missing.deep[?].x", "mask": "all"})
    if rng.random() < 0.3:
        rules.append({"path": "k0[9].v", "mask": "all"})
    return rules


class RandomDifferentialTests(unittest.TestCase):
    def test_matches_naive_implementation(self):
        rng = random.Random(20260921)
        for case in range(300):
            record = random_record(rng, depth=0)
            if not isinstance(record, dict):
                record = {"k0": record}
            rules = random_rules(rng, record)
            with self.subTest(case=case, rules=rules):
                expected = NaiveRedactor(rules).redact(copy.deepcopy(record))
                actual = Redactor(rules).redact(record)
                self.assertEqual(actual, expected)

    def test_hot_reload_matches_naive_implementation(self):
        rng = random.Random(97531)
        redactor = Redactor()
        for _ in range(50):
            record = random_record(rng, depth=0)
            if not isinstance(record, dict):
                record = {"k0": record}
            rules = random_rules(rng, record)
            redactor.load_rules(rules)
            expected = NaiveRedactor(rules).redact(copy.deepcopy(record))
            self.assertEqual(redactor.redact(record), expected)


class PerformanceTests(unittest.TestCase):
    def test_one_hundred_thousand_records_are_second_scale(self):
        record = {
            "user": {"id": 7, "phone": "13812345678"},
            "payments": [
                {"card": "6222020200112233", "amount": 12.5},
                {"card": "6222020200114455", "amount": 3},
            ],
        }
        redactor = Redactor([
            {"path": "user.phone", "mask": "phone"},
            {"path": "payments[?].card", "mask": "card"},
        ])
        start = time.perf_counter()
        for _ in range(100000):
            redactor.redact(record)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 5.0, "redacting 100k records took %rs" % elapsed)


if __name__ == "__main__":
    unittest.main()

    def test_original_does_not_land_without_bypass_sink(self):
        sink = MemorySink()
        pipeline = LogPipeline(sink)
        pipeline.set_redactor(Redactor(
            [{"path": "user.phone", "mask": "phone", "bypass": True}]
        ))
        pipeline.emit(sample_record())
        self.assertEqual(loads(sink.lines[0])["user"]["phone"], "138****5678")

    def test_bypass_rule_sends_original_only_for_matching_records(self):
        sink, bypass = MemorySink(), MemorySink()
        pipeline = LogPipeline(sink)
        pipeline.set_redactor(Redactor([
            {"path": "payments[?].card", "mask": "card", "bypass": True},
        ]))
        pipeline.set_bypass_sink(bypass)
        pipeline.emit({"user": {"phone": "13812345678"}})
        pipeline.emit(sample_record())
        self.assertEqual(len(bypass.lines), 1)
        self.assertEqual(
            loads(bypass.lines[0])["payments"][0]["card"], "6222020200112233"
        )
        self.assertEqual(
            loads(sink.lines[1])["payments"][0]["card"], "************2233"
        )
        self.assertEqual(
            loads(sink.lines[0])["user"]["phone"], "13812345678"
        )

    def test_shadowed_bypass_rule_does_not_bypass(self):
        sink, bypass = MemorySink(), MemorySink()
        pipeline = LogPipeline(sink)
        pipeline.set_redactor(Redactor([
            {"path": "payments[?].card", "mask": "card", "bypass": True},
            {"path": "payments[?].card", "mask": "phone"},
        ]))
        pipeline.set_bypass_sink(bypass)
        pipeline.emit(sample_record())
        self.assertEqual(bypass.lines, [])
