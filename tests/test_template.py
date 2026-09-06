import json
import re
import unittest
from html.parser import HTMLParser

import test_analyzer
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
    def test_period_labels_describe_the_selected_interval(self):
        fixture = test_analyzer.TestAnalyzer()
        fixture.setUp()
        data = analyze_data(fixture.sample_data)
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
            'Quotes " and \' & <angles> café 日本語 \u2028 \u2029',
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                fixture = test_analyzer.TestAnalyzer()
                fixture.setUp()
                fixture.sample_data["repo_meta"]["hs-buddy"]["description"] = payload
                data = analyze_data(fixture.sample_data)
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
