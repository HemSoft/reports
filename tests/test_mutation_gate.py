"""The mutation qualification boundary must reject poor and incomplete runs."""

import unittest

from scripts.check_mutations import qualifies, score_counts, target_spans


class TestMutationGate(unittest.TestCase):
    def test_break_threshold_and_incomplete_runs(self):
        self.assertEqual(score_counts({"killed": 8, "survived": 2}), 80)
        self.assertTrue(qualifies({"killed": 8, "survived": 2}, 80))
        self.assertFalse(qualifies({"killed": 7, "survived": 3}, 80))
        self.assertFalse(qualifies({"killed": 8, "timeout": 3}, 80))
        self.assertFalse(qualifies({"killed": 99, "error": 1}, 80))
        self.assertFalse(qualifies({"killed": 99, "pending": 1}, 80))
        self.assertFalse(qualifies({}, 80))

    def test_invalid_counts_are_rejected(self):
        for counts in ({"killed": -1}, {"killed": True}, {"unknown": 1}):
            with self.assertRaises(ValueError):
                score_counts(counts)

    def test_targets_follow_named_syntax_and_fail_if_removed_or_ambiguous(self):
        source = "\ndef choose(value):\n    return value\n\nmetric = (1 +\n          2)\n"
        targets = {"functions": ["choose"], "assignments": ["metric"]}
        self.assertEqual(target_spans(source, targets), [(2, 3), (5, 6)])
        with self.assertRaisesRegex(ValueError, "Missing mutation targets"):
            target_spans(source, {"functions": ["absent"], "assignments": []})
        with self.assertRaisesRegex(ValueError, "Ambiguous mutation target"):
            target_spans(source + "metric = 3\n", targets)


if __name__ == "__main__":
    unittest.main()
