"""Static report delivery and data integrity, without network requests."""

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import publish
from src.catalog import load_catalog, load_manifest
from src.landing import build_site

ROOT = Path(__file__).resolve().parents[1]
DUNE = ROOT / "editions" / "dune-awakening" / "2026-10-05"


class TestStaticEditions(unittest.TestCase):
    def test_dune_snapshot_embeds_the_archived_payload_without_changing_facts(self):
        manifest = load_manifest(DUNE / "manifest.json")
        data = json.loads(Path(manifest["payload"]).read_text(encoding="utf-8-sig"))
        page = Path(manifest["html"]).read_text(encoding="utf-8")
        embedded = re.search(
            r'<script id="loot-data" type="application/json">(.*?)</script>', page, re.S
        )
        self.assertEqual(json.loads(embedded[1]), data)
        self.assertEqual(manifest["edition"]["id"], data["checked"])
        self.assertEqual(len(data["items"]), 192)
        expected = {
            "Schematics": str(len(data["items"])),
            "Augments": str(sum(i["category"] == "Augment" for i in data["items"])),
            "Locations": str(len(data["stations"])),
            "S-tier items": str(sum(i["tier"] == "S" for i in data["items"])),
            "Database": data["databaseVersion"],
        }
        self.assertEqual(
            {h["label"]: h["value"] for h in manifest["edition"]["highlights"]}, expected
        )
        self.assertIn('href="../../../"', page)
        self.assertIn('href="payload.json"', page)
        self.assertIn("192 entries", page)

    def test_sync_creates_catalog_routes_and_keeps_original_publication_time(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(publish.sync_editions(folder, ROOT / "editions"), 1)
            before = (Path(folder) / "catalog.json").read_bytes()
            first = load_catalog(folder)["reports"][0]["editions"][0]
            with patch.object(publish, "datetime") as clock:
                clock.now.return_value.isoformat.return_value = "2027-01-01T00:00:00+00:00"
                self.assertEqual(
                    publish.main(["sync", folder, "--editions", str(ROOT / "editions")]), 0
                )
            self.assertEqual((Path(folder) / "catalog.json").read_bytes(), before)
            self.assertEqual(load_catalog(folder)["reports"][0]["editions"][0], first)
            build_site(folder)
            page = Path(folder) / "reports" / "dune-awakening" / "2026-10-05" / "index.html"
            self.assertEqual(page.read_bytes(), (DUNE / "report.html").read_bytes())
            self.assertEqual(
                page.with_name("payload.json").read_bytes(), (DUNE / "payload.json").read_bytes()
            )
            self.assertIn("Dune: Awakening", (Path(folder) / "index.html").read_text())
            redirect = Path(folder) / "reports" / "dune-awakening" / "index.html"
            self.assertIn("url=2026-10-05/", redirect.read_text())

    def test_sync_updates_an_edition_without_losing_other_report_series(self):
        with tempfile.TemporaryDirectory() as folder:
            publish.sync_editions(folder, ROOT / "editions")
            catalog = load_catalog(folder)
            catalog["reports"].append(
                {"id": "other", "title": "Other report", "summary": "Retained.", "editions": []}
            )
            (Path(folder) / "catalog.json").write_text(json.dumps(catalog))
            page = Path(folder) / "reports" / "dune-awakening" / "2026-10-05" / "index.html"
            page.write_text("outdated")
            publish.sync_editions(folder, ROOT / "editions")
            self.assertEqual(page.read_bytes(), (DUNE / "report.html").read_bytes())
            self.assertEqual(
                {r["id"] for r in load_catalog(folder)["reports"]}, {"dune-awakening", "other"}
            )

    def test_missing_source_fails_instead_of_silently_skipping_editions(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(publish.main(["sync", folder, "--editions", folder + "/missing"]), 1)
            self.assertFalse((Path(folder) / "catalog.json").exists())

    def test_incomplete_edition_fails_before_any_editions_are_published(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "editions"
            shutil.copytree(DUNE, source / "dune-awakening" / "2026-10-05")
            incomplete = source / "dune-awakening" / "2026-10-06"
            incomplete.mkdir()
            (incomplete / "manifest-misnamed.json").write_text("{}")
            site = Path(folder) / "site"
            self.assertEqual(publish.main(["sync", str(site), "--editions", str(source)]), 1)
            self.assertFalse(site.exists())
