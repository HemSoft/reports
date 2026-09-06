"""Behavior examples for the calculation and collection mutation targets."""

import copy
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

from report_fixture import load_report_fixture
from src.analyzer import _in_interval, analyze_data
from src.collector import CACHE_SCHEMA_VERSION, EDT, _cache_matches, _has_event, get_date_range


class TestMetricDecisions(unittest.TestCase):
    def test_fractional_rates_do_not_collapse_to_single_record_arithmetic(self):
        data = load_report_fixture()
        pr = data["prs"]["hs-buddy"][0]
        issue = data["issues"]["hs-buddy"][0]
        data["prs"] = {"hs-buddy": [dict(pr, state=s) for s in ["MERGED", "OPEN", "CLOSED"]]}
        data["issues"] = {"hs-buddy": [dict(issue, state=s) for s in ["CLOSED", "OPEN", "OPEN"]]}
        kpis = analyze_data(data)["kpis"]
        self.assertEqual(kpis["pr_merge_rate"], 33.3)
        self.assertEqual(kpis["issue_close_rate"], 33.3)

    def test_cycle_average_median_and_each_distribution_boundary(self):
        data = load_report_fixture()
        pr = data["prs"]["hs-buddy"][0]
        cycles = [0.125, 1, 3.75, 4, 23.75, 24, 71.75, 72, 100.125]
        data["prs"] = {"hs-buddy": [dict(pr, cycle_hours=h) for h in cycles]}
        kpis = analyze_data(data)["kpis"]
        self.assertEqual(kpis["avg_pr_cycle_hours"], 33.39)
        self.assertEqual(kpis["median_pr_cycle_hours"], 23.75)
        self.assertEqual(
            kpis["pr_cycle_distribution"],
            {"under_1h": 1, "1h_to_4h": 2, "4h_to_24h": 2, "1d_to_3d": 2, "over_3d": 2},
        )
        data["prs"] = {"hs-buddy": [dict(pr, cycle_hours=1.234)]}
        kpis = analyze_data(data)["kpis"]
        self.assertEqual(kpis["avg_pr_cycle_hours"], 1.23)
        self.assertEqual(kpis["median_pr_cycle_hours"], 1.23)

    def test_no_activity_has_zero_rates_and_no_cycle_buckets(self):
        data = load_report_fixture()
        data.update(commits=[], prs={}, issues={})
        kpis = analyze_data(data)["kpis"]
        for key in [
            "pr_merge_rate",
            "issue_close_rate",
            "avg_pr_cycle_hours",
            "median_pr_cycle_hours",
        ]:
            self.assertEqual(kpis[key], 0)
        self.assertEqual(list(kpis["pr_cycle_distribution"].values()), [0, 0, 0, 0, 0])

    def test_interval_decisions_include_both_endpoints_and_any_matching_event(self):
        start = datetime(2026, 9, 1, tzinfo=EDT)
        end = start + timedelta(days=1)
        for date, expected in [
            (start - timedelta(seconds=1), False),
            (start, True),
            (start + timedelta(hours=12), True),
            (end, True),
            (end + timedelta(seconds=1), False),
        ]:
            stamp = date.isoformat()
            with self.subTest(stamp=stamp):
                self.assertEqual(_in_interval(stamp, start, end), expected)
                self.assertEqual(_has_event({"created": stamp}, ["created"], start, end), expected)
        self.assertFalse(_in_interval(None, start, end))
        self.assertFalse(_has_event({}, ["created", "closed"], start, end))
        self.assertTrue(
            _has_event(
                {"created": None, "closed": end.isoformat()}, ["created", "closed"], start, end
            )
        )

    def test_relative_and_same_day_date_ranges_preserve_full_day_endpoints(self):
        now = datetime(2026, 9, 5, 14, 35, 42, 123456, tzinfo=EDT)
        with patch("src.collector.datetime", wraps=datetime) as clock:
            clock.now.return_value = now
            self.assertEqual(
                get_date_range(weeks=2),
                (datetime(2026, 8, 22, tzinfo=EDT), datetime(2026, 9, 5, 23, 59, 59, tzinfo=EDT)),
            )
        self.assertEqual(
            get_date_range(start_str="2026-09-01", end_str="2026-09-01"),
            (datetime(2026, 9, 1, tzinfo=EDT), datetime(2026, 9, 1, 23, 59, 59, tzinfo=EDT)),
        )

    def test_cache_completeness_requires_boolean_true_and_exact_interval(self):
        inputs = {"start_iso": "2026-09-01", "end_iso": "2026-09-02", "weeks": 1}
        data = {
            "cache_schema_version": CACHE_SCHEMA_VERSION,
            "cache_inputs": inputs,
            "collection_complete": True,
            "range": dict(inputs),
            "commits": [],
            "prs": {},
            "issues": {},
            "repo_meta": {},
        }
        self.assertTrue(_cache_matches(data, dict(inputs)))
        for value in [None, False, 0, 1, "true"]:
            self.assertFalse(_cache_matches(dict(data, collection_complete=value), inputs))
        for key in inputs:
            changed = copy.deepcopy(data)
            changed["range"][key] = "different"
            self.assertFalse(_cache_matches(changed, inputs), key)


if __name__ == "__main__":
    unittest.main()
