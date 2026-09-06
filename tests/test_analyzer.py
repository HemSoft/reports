import unittest
import copy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from src.analyzer import analyze_data

EDT = ZoneInfo("America/New_York")

class TestAnalyzer(unittest.TestCase):
    def setUp(self):
        self.sample_data = {
            "range": {
                "weeks": 2,
                "start_iso": "2026-08-22T00:00:00-04:00",
                "end_iso": "2026-09-05T23:59:59-04:00",
                "start_date": "2026-08-22",
                "end_date": "2026-09-05",
                "start_formatted": "Aug 22, 2026",
                "end_formatted": "Sep 05, 2026"
            },
            "commits": [
                {
                    "hash": "abc1234",
                    "repo": "hs-buddy",
                    "author_name": "Franz Hemmer",
                    "author_email": "franz_hemmer@hotmail.com",
                    "author_category": "Human (Franz Hemmer)",
                    "author_date": "2026-09-01T14:30:00-04:00",
                    "timestamp": 1788287400,
                    "day_of_week": "Tuesday",
                    "day_index": 1,
                    "hour": 14,
                    "date_str": "2026-09-01",
                    "subject": "feat: test feature",
                    "category": "Feature",
                    "additions": 100,
                    "deletions": 20,
                    "net_lines": 80,
                    "files": [{"path": "src/index.ts", "adds": 100, "dels": 20, "language": "TypeScript"}]
                },
                {
                    "hash": "def5678",
                    "repo": "hs-buddy",
                    "author_name": "Franz Hemmer",
                    "author_email": "franz_hemmer@hotmail.com",
                    "author_category": "Human (Franz Hemmer)",
                    "author_date": "2026-09-02T23:15:00-04:00",
                    "timestamp": 1788405300,
                    "day_of_week": "Wednesday",
                    "day_index": 2,
                    "hour": 23,
                    "date_str": "2026-09-02",
                    "subject": "fix: bugfix",
                    "category": "Bug Fix",
                    "additions": 10,
                    "deletions": 5,
                    "net_lines": 5,
                    "files": [{"path": "src/app.ts", "adds": 10, "dels": 5, "language": "TypeScript"}]
                }
            ],
            "prs": {
                "hs-buddy": [
                    {
                        "number": 1,
                        "title": "feat: test feature PR",
                        "state": "MERGED",
                        "createdAt": "2026-09-01T14:00:00Z",
                        "mergedAt": "2026-09-01T14:30:00Z",
                        "cycle_hours": 0.5,
                        "repo": "hs-buddy"
                    }
                ]
            },
            "issues": {
                "hs-buddy": [
                    {
                        "number": 10,
                        "title": "issue 10",
                        "state": "CLOSED",
                        "createdAt": "2026-09-01T10:00:00Z",
                        "closedAt": "2026-09-01T14:30:00Z",
                        "repo": "hs-buddy"
                    }
                ]
            },
            "repo_meta": {
                "hs-buddy": {
                    "name": "hs-buddy",
                    "isPrivate": False,
                    "description": "Buddy Workbench",
                    "stargazerCount": 5,
                    "forkCount": 1
                }
            }
        }

    def test_analyzer_kpis(self):
        res = analyze_data(self.sample_data)
        kpis = res["kpis"]
        self.assertEqual(kpis["total_commits"], 2)
        self.assertEqual(kpis["total_additions"], 110)
        self.assertEqual(kpis["total_deletions"], 25)
        self.assertEqual(kpis["net_lines"], 85)
        self.assertEqual(kpis["total_prs"], 1)
        self.assertEqual(kpis["merged_prs"], 1)
        self.assertEqual(kpis["pr_merge_rate"], 100.0)
        self.assertEqual(kpis["total_issues"], 1)
        self.assertEqual(kpis["closed_issues"], 1)
        self.assertEqual(kpis["issue_close_rate"], 100.0)
        self.assertEqual(kpis["active_days_count"], 2)

    def test_night_owl_calculation(self):
        res = analyze_data(self.sample_data)
        kpis = res["kpis"]
        # One commit is at hour 23 (night owl), one at hour 14 (afternoon)
        self.assertEqual(kpis["day_parts"]["night_owl"], 1)
        self.assertEqual(kpis["day_parts"]["afternoon"], 1)
        self.assertEqual(kpis["night_owl_ratio"], 50.0)

    def test_weekly_buckets_include_each_day_and_event_once(self):
        data = self.sample_data
        commit = data["commits"][0]
        pr = data["prs"]["hs-buddy"][0]
        issue = data["issues"]["hs-buddy"][0]
        data["commits"] = []
        data["prs"]["hs-buddy"] = []
        data["issues"]["hs-buddy"] = []
        start = datetime.fromisoformat(data["range"]["start_iso"])
        for day in range(15):
            date = start + timedelta(days=day, hours=12)
            data["commits"].append(dict(
                commit, hash=str(day), author_date=date.isoformat(),
                date_str=date.strftime("%Y-%m-%d"), day_index=date.weekday(),
                day_of_week=date.strftime("%A"), hour=12))
            timestamp = date.astimezone(ZoneInfo("UTC")).isoformat()
            data["prs"]["hs-buddy"].append(dict(
                pr, number=day, createdAt=timestamp, mergedAt=timestamp))
            data["issues"]["hs-buddy"].append(dict(
                issue, number=day, createdAt=timestamp, closedAt=timestamp))
        result = analyze_data(data)
        buckets = result["weekly_data"]
        self.assertEqual([b["commits"] for b in buckets], [7, 7, 1])
        covered_days = []
        for bucket in buckets:
            first = datetime.fromisoformat(bucket["start_date"])
            last = datetime.fromisoformat(bucket["end_date"])
            covered_days.extend(first + timedelta(days=d)
                                for d in range((last - first).days + 1))
            self.assertLessEqual(first, last)
        self.assertEqual(len(covered_days), len(set(covered_days)))
        self.assertEqual(len(covered_days), 15)
        self.assertEqual(buckets[-1]["end_date"], data["range"]["end_date"])
        for metric in ["commits", "prs_opened", "prs_merged", "issues_closed"]:
            self.assertEqual(sum(b[metric] for b in buckets), 15, metric)

    def test_custom_range_does_not_use_default_week_count(self):
        self.sample_data["range"].update(
            weeks=12, start_iso="2026-01-01T00:00:00-05:00",
            end_iso="2026-01-02T23:59:59-05:00")
        self.sample_data["commits"] = []
        buckets = analyze_data(self.sample_data)["weekly_data"]
        self.assertEqual(len(buckets), 1)
        self.assertEqual(buckets[0]["start_date"], "2026-01-01")
        self.assertEqual(buckets[0]["end_date"], "2026-01-02")

    def test_utc_and_eastern_events_share_dst_boundary_buckets(self):
        cases = [
            ("2026-03-02T00:00:00-05:00", "2026-03-15T23:59:59-04:00",
             "2026-03-09T03:30:00Z", "2026-03-08T23:30:00-04:00"),
            ("2026-10-26T00:00:00-04:00", "2026-11-08T23:59:59-05:00",
             "2026-11-02T04:30:00Z", "2026-11-01T23:30:00-05:00"),
            ("2026-09-01T00:00:00-04:00", "2026-09-14T23:59:59-04:00",
             "2026-09-08T02:00:00Z", "2026-09-07T22:00:00-04:00"),
        ]
        for start, end, utc, eastern in cases:
            with self.subTest(start=start):
                data = copy.deepcopy(self.sample_data)
                data["range"].update(start_iso=start, end_iso=end)
                data["commits"] = []
                pr = data["prs"]["hs-buddy"][0]
                issue = data["issues"]["hs-buddy"][0]
                data["prs"]["hs-buddy"] = [
                    dict(pr, createdAt=t, mergedAt=t) for t in [utc, eastern]]
                data["issues"]["hs-buddy"] = [
                    dict(issue, closedAt=t) for t in [utc, eastern]]
                buckets = analyze_data(data)["weekly_data"]
                for metric in ["prs_opened", "prs_merged", "issues_closed"]:
                    self.assertEqual([b[metric] for b in buckets], [2, 0])

    def test_empty_commit_profiles_handle_missing_null_and_empty_language(self):
        from src.template import build_html_report
        for metadata in ({}, {"primaryLanguage": None}, {"primaryLanguage": {}},
                         {"primaryLanguage": ""}, {"primaryLanguage": {"name": None}},
                         {"primaryLanguage": {"name": ""}}):
            with self.subTest(metadata=metadata):
                data = copy.deepcopy(self.sample_data)
                data["commits"] = [dict(data["commits"][0], files=[], additions=0, deletions=0, net_lines=0)]
                data["repo_meta"]["hs-buddy"] = metadata
                analysis = analyze_data(data)
                self.assertEqual(analysis["repo_profiles"][0]["primary_language"], "Unknown")
                self.assertEqual(analysis["repo_profiles"][0]["commits"], 1)
                self.assertIn("Unknown", build_html_report(analysis))

    def test_profile_language_uses_churn_then_metadata(self):
        data = copy.deepcopy(self.sample_data)
        data["repo_meta"]["hs-buddy"]["primaryLanguage"] = {"name": "Python"}
        self.assertEqual(analyze_data(data)["repo_profiles"][0]["primary_language"], "TypeScript")
        for commit in data["commits"]:
            commit.update(files=[], additions=0, deletions=0, net_lines=0)
        self.assertEqual(analyze_data(data)["repo_profiles"][0]["primary_language"], "Python")

    def test_median_cycle_time_for_even_odd_empty_and_single_samples(self):
        cases = [([0.5, 3.5], 2.0), ([3.5, 0.5, 2.0], 2.0), ([], 0.0),
                 ([0.5], 0.5), ([0.501, 3.519], 2.01), ([None, 0.5], 0.5)]
        for values, expected in cases:
            with self.subTest(values=values):
                data = copy.deepcopy(self.sample_data)
                example = data["prs"]["hs-buddy"][0]
                data["prs"]["hs-buddy"] = [dict(example, number=i+1, cycle_hours=value)
                                             for i, value in enumerate(values)]
                self.assertEqual(analyze_data(data)["kpis"]["median_pr_cycle_hours"], expected)

if __name__ == "__main__":
    unittest.main()
