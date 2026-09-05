import unittest
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

if __name__ == "__main__":
    unittest.main()
