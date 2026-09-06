import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.summarize_benchmark import main


class TestBenchmarkSummary(unittest.TestCase):
    def test_reported_rss_max_includes_a_higher_baseline(self):
        report = {
            "revision": "fixture",
            "dirty": False,
            "mode": "pr",
            "environment": {"platform": "fixture", "browser": "fixture"},
            "cases": [
                {
                    "id": "baseline-peak",
                    "samples": [
                        {
                            "readyMs": 1,
                            "frameP95Ms": 1,
                            "taskMsPerSecond": 1,
                            "baseline": {"heapBytes": 100, "processes": [{"rssBytes": 70_000_000}]},
                            "retained": [
                                {"heapBytes": 100, "processes": [{"rssBytes": 10_000_000}]}
                            ],
                        }
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.json"
            path.write_text(json.dumps(report), encoding="utf-8")
            with patch("sys.argv", ["summarize_benchmark.py", str(path)]):
                main()
            row = next(
                line
                for line in path.with_suffix(".md").read_text(encoding="utf-8").splitlines()
                if line.startswith("| baseline-peak")
            )
            self.assertEqual(float(row.split("|")[-2]), 70.0)
