"""Regression controls for the risk gate's calculation and failure boundaries."""

import copy
import tempfile
from pathlib import Path
import unittest

from scripts.check_risk import crap_score, measure, violations


class TestRiskGate(unittest.TestCase):
    def test_formula_and_boundaries(self):
        self.assertEqual(crap_score(10, 0), 110)
        self.assertEqual(crap_score(10, 0.5), 22.5)
        self.assertEqual(crap_score(10, 1), 10)
        for complexity, coverage in [(0, 1), (1, -0.1), (1, 1.1)]:
            with self.assertRaises(ValueError):
                crap_score(complexity, coverage)

    def test_new_high_risk_existing_regression_and_worst_regression_fail(self):
        baseline = {"worst": 50, "functions": {"legacy": 50}}
        self.assertEqual(violations([{"function": "new", "crap": 30}], baseline), [])
        self.assertTrue(violations([{"function": "new", "crap": 31}], baseline))
        self.assertTrue(violations([{"function": "legacy", "crap": 51}], baseline))
        self.assertEqual(violations([{"function": "legacy", "crap": 49}], baseline), [])
        self.assertTrue(
            violations([{"function": "new", "crap": 29}], {"worst": 28, "functions": {}})
        )

    def test_lowered_legacy_cap_is_honored_below_actionable_threshold(self):
        baseline = {"worst": 50, "functions": {"improved": 20, "other": 50}}
        self.assertEqual(violations([{"function": "improved", "crap": 20}], baseline), [])
        self.assertTrue(violations([{"function": "improved", "crap": 21}], baseline))
        self.assertEqual(violations([{"function": "new", "crap": 30}], baseline), [])

    def test_branch_ratio_is_not_combined_line_percentage_and_untested_is_visible(self):
        source = "def choice(value):\n    if value:\n        return 1\n    return 0\n\ndef untested():\n    return 1\n"
        functions = {
            "choice": {
                "start_line": 1,
                "summary": {
                    "num_branches": 2,
                    "covered_branches": 1,
                    "num_statements": 3,
                    "covered_lines": 2,
                },
            },
            "untested": {
                "start_line": 6,
                "summary": {
                    "num_branches": 0,
                    "covered_branches": 0,
                    "num_statements": 1,
                    "covered_lines": 0,
                },
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "cli.py").write_text(source, encoding="utf-8")
            data = {
                "meta": {"branch_coverage": True},
                "files": {"cli.py": {"functions": functions}},
            }
            rows = {row["function"]: row for row in measure(root, data)}
            self.assertEqual(rows["cli.py:choice"]["coverage"], 0.5)
            self.assertEqual(rows["cli.py:choice"]["crap"], 2.5)
            self.assertEqual(rows["cli.py:untested"]["coverage"], 0)
            self.assertEqual(rows["cli.py:untested"]["crap"], 2)
            missing = copy.deepcopy(data)
            del missing["files"]["cli.py"]["functions"]["untested"]
            with self.assertRaisesRegex(ValueError, "Cannot match coverage"):
                measure(root, missing)
            with self.assertRaises(KeyError):
                measure(root, {"meta": data["meta"], "files": {}})
            data["meta"]["branch_coverage"] = False
            with self.assertRaisesRegex(ValueError, "Branch coverage is required"):
                measure(root, data)


if __name__ == "__main__":
    unittest.main()
