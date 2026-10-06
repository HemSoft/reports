import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import cli
import publish
from report_fixture import load_report_fixture
from src.analyzer import analyze_data
from src.catalog import load_catalog, load_manifest
from src.generator import _hours, _signed, edition_manifest, generate_report


class TestProductivityEdition(unittest.TestCase):
    def test_manifest_describes_the_edition(self):
        manifest = edition_manifest(analyze_data(load_report_fixture()))
        self.assertEqual(manifest["report"]["id"], "productivity")
        self.assertEqual(manifest["edition"]["id"], "2026-09-05")
        self.assertEqual(manifest["edition"]["title"], "2 weeks to Sep 05, 2026")
        labels = [h["label"] for h in manifest["edition"]["highlights"]]
        self.assertEqual(labels[0], "Commits")
        self.assertEqual(len(labels), 6)

    def test_highlight_formatting(self):
        self.assertEqual(_signed(-2_501_295), "−2.50M")
        self.assertEqual(_signed(12345), "+12,345")
        self.assertEqual(_hours(0.5), "30 min")
        self.assertEqual(_hours(26.25), "26.2 h")

    def test_generator_writes_publishable_edition(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("src.generator.collect_all", return_value=load_report_fixture()),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            edition = os.path.join(tmp, "edition")
            generate_report(
                base_dir=tmp,
                weeks=2,
                output_html=os.path.join(tmp, "standalone.html"),
                edition_dir=edition,
            )
            manifest = load_manifest(os.path.join(edition, "manifest.json"))
            with open(manifest["html"], encoding="utf-8") as f:
                report = f.read()
            with open(os.path.join(tmp, "standalone.html"), encoding="utf-8") as f:
                standalone = f.read()
            with open(manifest["payload"], encoding="utf-8") as f:
                payload = json.load(f)
        self.assertIn('<a class="btn" href="../../../">All reports</a>', report)
        self.assertNotIn("All reports", standalone)
        self.assertEqual(payload["kpis"]["total_commits"], 2)


class TestCommandLines(unittest.TestCase):
    def test_report_cli_forwards_edition_dir(self):
        with (
            patch("sys.argv", ["cli.py", "--edition-dir", "edition"]),
            patch("cli.generate_report", return_value=("out.html", {})) as generate,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            cli.main()
        self.assertEqual(generate.call_args.kwargs["edition_dir"], "edition")

    def test_publish_add_then_build(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("src.generator.collect_all", return_value=load_report_fixture()),
            contextlib.redirect_stdout(io.StringIO()) as out,
        ):
            edition = os.path.join(tmp, "edition")
            site = os.path.join(tmp, "site")
            generate_report(
                base_dir=tmp, weeks=2, output_html=os.path.join(tmp, "x.html"), edition_dir=edition
            )
            manifest = os.path.join(edition, "manifest.json")
            stamp = ["--published-at", "2026-09-07T12:00:00+00:00"]
            self.assertEqual(publish.main(["add", site, "--manifest", manifest, *stamp]), 0)
            self.assertEqual(publish.main(["build", site]), 0)
            self.assertEqual(publish.main(["add", site, "--manifest", manifest]), 0)
            catalog = load_catalog(site)
            self.assertTrue(os.path.exists(os.path.join(site, "index.html")))
        self.assertIn("Published productivity edition 2026-09-05", out.getvalue())
        self.assertEqual(len(catalog["reports"][0]["editions"]), 1)
        self.assertNotEqual(catalog["reports"][0]["editions"][0]["published_at"], stamp[1])

    def test_publish_reports_failures(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()) as err:
            code = publish.main(["add", tmp, "--manifest", os.path.join(tmp, "missing.json")])
        self.assertEqual(code, 1)
        self.assertIn("add failed", err.getvalue())


if __name__ == "__main__":
    unittest.main()
