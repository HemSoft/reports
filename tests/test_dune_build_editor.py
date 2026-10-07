"""Publication and reproducibility checks for the standalone build editor."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from publish import sync_editions
from src.catalog import load_catalog
from src.landing import build_site

ROOT = Path(__file__).resolve().parents[1]
EDITION = ROOT / "editions/dune-awakening-build-editor/2026-10-06"


class BuildEditorPublicationTests(unittest.TestCase):
    def test_generated_page_matches_sources_and_contains_snapshot(self):
        spec = importlib.util.spec_from_file_location(
            "dune_build_page", ROOT / "scripts/dune-build/build.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        page = (EDITION / "report.html").read_text(encoding="utf-8")
        self.assertEqual(page, module.render())
        self.assertNotIn("<script src=", page)
        embedded = page.split('<script type="application/json" id="build-data">', 1)[1].split(
            "</script>", 1
        )[0]
        self.assertEqual(json.loads(embedded), json.loads((EDITION / "payload.json").read_text()))

    def test_editor_and_loot_report_publish_as_distinct_series(self):
        with tempfile.TemporaryDirectory() as site:
            sync_editions(site, str(ROOT / "editions"))
            build_site(site)
            reports = {report["id"]: report for report in load_catalog(site)["reports"]}
            self.assertIn("dune-awakening", reports)
            self.assertIn("dune-awakening-build-editor", reports)
            folder = Path(site) / "reports/dune-awakening-build-editor"
            self.assertIn("url=2026-10-06/", (folder / "index.html").read_text())
            self.assertEqual(
                (folder / "2026-10-06/index.html").read_bytes(),
                (EDITION / "report.html").read_bytes(),
            )
            index = (Path(site) / "index.html").read_text()
            self.assertIn('href="reports/dune-awakening-build-editor/"', index)
            self.assertIn('href="reports/dune-awakening/"', index)

    def test_snapshot_has_unique_ids_and_complete_rank_and_augment_data(self):
        data = json.loads((EDITION / "payload.json").read_text())
        for collection in ("items", "augments", "skills", "tracks"):
            identifiers = [record["id"] for record in data[collection]]
            self.assertEqual(len(identifiers), len(set(identifiers)))
        tags = {skill["tag"] for skill in data["skills"]}
        for skill in data["skills"]:
            self.assertEqual(len(skill["costPerLevel"]), skill["maxLevel"])
            self.assertTrue(set(skill["prerequisites"]).issubset(tags))
        for augment in data["augments"]:
            self.assertTrue(augment["stats"])
            for stat in augment["stats"]:
                self.assertIn(stat["operation"], ("add", "multiply", "set"))
                self.assertTrue(all(1 <= row["quality"] <= 5 for row in stat["values"]))
