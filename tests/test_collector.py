import unittest
from zoneinfo import ZoneInfo
from src.collector import get_date_range, detect_language, classify_commit, categorize_author

EDT = ZoneInfo("America/New_York")


class TestCollector(unittest.TestCase):
    def test_date_range_calculation(self):
        start_dt, end_dt = get_date_range(weeks=12)
        diff_days = (end_dt.date() - start_dt.date()).days
        self.assertEqual(diff_days, 84)

    def test_custom_date_range(self):
        start_dt, end_dt = get_date_range(start_str="2026-01-01", end_str="2026-01-31")
        self.assertEqual(start_dt.strftime("%Y-%m-%d"), "2026-01-01")
        self.assertEqual(end_dt.strftime("%Y-%m-%d"), "2026-01-31")

    def test_invalid_ranges_are_rejected(self):
        for args in [
            dict(weeks=0),
            dict(weeks=-1),
            dict(start_str="2026-01-01"),
            dict(end_str="2026-01-01"),
            dict(start_str="2026-01-02", end_str="2026-01-01"),
        ]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                get_date_range(**args)

    def test_language_detection(self):
        self.assertEqual(detect_language("main.swift"), "Swift")
        self.assertEqual(detect_language("app.tsx"), "TypeScript (React)")
        self.assertEqual(detect_language("server.go"), "Go")
        self.assertEqual(detect_language("script.py"), "Python")
        self.assertEqual(detect_language("Dockerfile"), "Docker")
        self.assertEqual(detect_language("README.md"), "Markdown")

    def test_commit_classification(self):
        self.assertEqual(classify_commit("feat: add active repository workbench", []), "Feature")
        self.assertEqual(
            classify_commit("fix(bookmarks): replace stalled loading with retry", []), "Bug Fix"
        )
        self.assertEqual(classify_commit("refactor: split parser routines", []), "Refactoring")
        self.assertEqual(classify_commit("docs: update architecture guide", []), "Documentation")
        self.assertEqual(classify_commit("test: cover monitor state transitions", []), "Testing")
        self.assertEqual(classify_commit("ci: enforce CodeQL scanning", []), "CI / DevOps")
        self.assertEqual(
            classify_commit("chore(deps): bump convex from 1.44.0 to 1.45.0", []),
            "Chore / Maintenance",
        )
        self.assertEqual(
            classify_commit("add ralph loop autonomous step", []), "Agent / Automation"
        )

    def test_author_categorization(self):
        self.assertEqual(
            categorize_author("Franz Hemmer", "franz_hemmer@hotmail.com"), "Human (Franz Hemmer)"
        )
        self.assertEqual(categorize_author("Copilot", "copilot@github.com"), "AI Copilot")
        self.assertEqual(
            categorize_author("Cursor Agent", "cursoragent@cursor.com"), "AI Agent (Cursor)"
        )
        self.assertEqual(
            categorize_author("dependabot[bot]", "dependabot@github.com"), "Dependabot"
        )


if __name__ == "__main__":
    unittest.main()
