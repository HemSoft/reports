"""The mutation qualification boundary must reject poor and incomplete runs."""

import unittest
from pathlib import Path
import tempfile

from cosmic_ray.work_db import use_db
from cosmic_ray.work_item import MutationSpec, TestOutcome, WorkerOutcome, WorkItem, WorkResult

from scripts.check_mutations import qualifies, score_counts, summarize, target_spans


class TestMutationGate(unittest.TestCase):
    def test_cosmic_ray_database_outcomes_are_classified_without_crediting_timeouts(self):
        results = [
            WorkResult(WorkerOutcome.NORMAL, test_outcome=TestOutcome.KILLED),
            WorkResult(WorkerOutcome.NORMAL, test_outcome=TestOutcome.SURVIVED),
            WorkResult(WorkerOutcome.NORMAL, output="timeout", test_outcome=TestOutcome.KILLED),
            WorkResult(WorkerOutcome.NORMAL, test_outcome=TestOutcome.INCOMPETENT),
            WorkResult(WorkerOutcome.EXCEPTION),
        ]
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "results.sqlite"
            with use_db(database) as db:
                for index in range(6):
                    mutation = MutationSpec(
                        Path("src/example.py"), "core/example", index, (1, 0), (1, 1)
                    )
                    db.add_work_item(WorkItem.single(str(index), mutation))
                    if index < len(results):
                        db.set_result(str(index), results[index])
            report = summarize(database, excluded=3)
        self.assertEqual(
            report["counts"], {"killed": 1, "survived": 1, "timeout": 1, "error": 2, "pending": 1}
        )
        self.assertEqual(report["excluded"], 3)
        self.assertAlmostEqual(report["score"], 100 / 6)
        self.assertFalse(qualifies(report["counts"], 10))

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
