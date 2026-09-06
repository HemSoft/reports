import json
import re
import unittest
from datetime import datetime
from html.parser import HTMLParser

from report_fixture import load_report_fixture
from src.analyzer import analyze_data
from src.template import build_html_report


class ScriptParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.in_script = False

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.in_script = True
            self.scripts.append("")

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False

    def handle_data(self, data):
        if self.in_script:
            self.scripts[-1] += data


class TestTemplate(unittest.TestCase):
    def test_generation_timestamp_uses_eastern_season_and_source_freshness(self):
        for timestamp, expected in [
            ("2026-09-05T12:00:00-04:00", "Sep 05, 2026 12:00:00 EDT (UTC-0400)"),
            ("2026-01-08T02:30:00Z", "Jan 07, 2026 21:30:00 EST (UTC-0500)"),
            ("2026-03-08T06:59:59Z", "Mar 08, 2026 01:59:59 EST (UTC-0500)"),
            ("2026-03-08T07:00:00Z", "Mar 08, 2026 03:00:00 EDT (UTC-0400)"),
            (None, "Unknown"),
        ]:
            with self.subTest(timestamp=timestamp):
                raw = load_report_fixture()
                raw["generated_at"] = timestamp
                data = analyze_data(raw)
                report = build_html_report(data)
                self.assertIn(f"Data generated: <strong>{expected}</strong>", report)
                self.assertIn("America/New_York (ET)", report)
                self.assertIn("Day × Hour Matrix ET", report)
                self.assertIn("Date (ET)", report)
                self.assertIn("Commits by Hour (ET)", report)
                self.assertEqual(data["generated_at"], timestamp)

    def test_generation_timestamp_without_offset_is_rejected(self):
        data = analyze_data(load_report_fixture())
        data["generated_at"] = "2026-01-08T02:30:00"
        with self.assertRaisesRegex(ValueError, "generated_at must include a timezone"):
            build_html_report(data)

    def test_cycle_subtitle_uses_measured_merged_prs(self):
        for cycles, expected in [([], "0.0"), ([0.5], "100.0"), ([0.5, 1, 4], "33.3")]:
            with self.subTest(cycles=cycles):
                raw = load_report_fixture()
                prototype = raw["prs"]["hs-buddy"][0]
                raw["prs"]["hs-buddy"] = [
                    dict(prototype, cycle_hours=hours) for hours in cycles
                ] + [
                    dict(prototype, cycle_hours=None),
                    dict(prototype, state="OPEN", cycle_hours=0.5),
                ]
                report = build_html_report(analyze_data(raw))
                self.assertIn(f"({expected}% under 1 hour; measured merged PRs)", report)
                self.assertNotIn("58.7%", report)
        raw["prs"] = {}
        self.assertIn(
            "(0.0% under 1 hour; measured merged PRs)", build_html_report(analyze_data(raw))
        )

    def test_header_subtitle_and_footer_match_short_and_explicit_periods(self):
        for start, end, weeks in [
            ("2026-09-01T00:00:00-04:00", "2026-09-07T23:59:59-04:00", 1),
            ("2026-08-22T00:00:00-04:00", "2026-09-05T23:59:59-04:00", 2),
            ("2026-01-03T00:00:00-05:00", "2026-01-05T23:59:59-05:00", 12),
        ]:
            with self.subTest(start=start, end=end):
                raw = load_report_fixture()
                start_dt, end_dt = datetime.fromisoformat(start), datetime.fromisoformat(end)
                first, last = start_dt.strftime("%b %d, %Y"), end_dt.strftime("%b %d, %Y")
                raw["range"].update(
                    start_iso=start,
                    end_iso=end,
                    weeks=weeks,
                    start_formatted=first,
                    end_formatted=last,
                )
                report = build_html_report(analyze_data(raw))
                self.assertIn(f"Period: <strong>{first} – {last}</strong>", report)
                self.assertIn(f"cumulative lines added from {first} through {last}", report)
                self.assertIn(f"Audited Period: {first} – {last}", report)
                self.assertNotRegex(report, r"12[- ](?:Week|week)")

    def test_period_labels_describe_the_selected_interval(self):
        data = analyze_data(load_report_fixture())
        report = build_html_report(data)
        self.assertIn("cumulative lines added from Aug 22, 2026 through Sep 05, 2026", report)
        self.assertNotIn("across 12 consecutive weeks", report)
        self.assertNotIn("12-Week Period", report)
        self.assertNotIn("12-week audit window", report)
        self.assertNotIn("(12 Weeks)", report)

    def test_metadata_cannot_terminate_script_and_round_trips(self):
        payloads = [
            "</script><script>document.documentElement.dataset.auditProbe=1</script>",
            "</ScRiPt><script>document.documentElement.dataset.auditProbe=1</script>",
            "<!-- <script> nested </script> -->",
            "Quotes \" and ' & <angles> café 日本語 \u2028 \u2029",
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                fixture_data = load_report_fixture()
                fixture_data["repo_meta"]["hs-buddy"]["description"] = payload
                data = analyze_data(fixture_data)
                data["author_distribution"] = {payload: 2}
                data["category_distribution"] = {payload: 2}
                data["weekly_data"][0]["top_repo"] = payload
                parser = ScriptParser()
                parser.feed(build_html_report(data))
                self.assertEqual(len(parser.scripts), 4)
                script = parser.scripts[-1]
                self.assertNotIn("<", script.split("// ===", 1)[0])
                expected = {
                    "weeklyData": data["weekly_data"],
                    "repoData": data["repo_profiles"],
                    "langData": data["language_breakdown"],
                    "temporalData": data["temporal"],
                    "matrix7x24": data["temporal"]["matrix_7x24"],
                    "catData": data["category_distribution"],
                    "authorData": data["author_distribution"],
                    "kpiData": data["kpis"],
                }
                for name, value in expected.items():
                    match = re.search(rf"const {name} = (.*);", script)
                    self.assertIsNotNone(match, name)
                    # JSON object keys are strings, including integer hour keys.
                    self.assertEqual(json.loads(match.group(1)), json.loads(json.dumps(value)))


if __name__ == "__main__":
    unittest.main()
