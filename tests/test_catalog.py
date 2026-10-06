import json
import os
import tempfile
import unittest

from src.catalog import (
    CatalogError,
    add_edition,
    edition_count,
    latest,
    load_catalog,
    load_manifest,
    publish,
    save_catalog,
)


def write_manifest(folder, report_id="ops", edition_id="2026-10-05", **overrides):
    with open(os.path.join(folder, "report.html"), "w", encoding="utf-8") as f:
        f.write("<html>report</html>")
    with open(os.path.join(folder, "payload.json"), "w", encoding="utf-8") as f:
        f.write('{"value": 1}')
    manifest = {
        "report": {"id": report_id, "title": "Ops Review", "summary": "Weekly operations."},
        "edition": {
            "id": edition_id,
            "title": "Week 40",
            "period": {"start": "Sep 29, 2026", "end": "Oct 05, 2026"},
            "highlights": [{"label": "Incidents", "value": "0"}],
        },
        "files": {"html": "report.html", "payload": "payload.json"},
    }
    manifest.update(overrides)
    path = os.path.join(folder, f"{report_id}-{edition_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    return path


class TestManifest(unittest.TestCase):
    def test_valid_manifest_resolves_files_next_to_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = load_manifest(write_manifest(tmp))
        self.assertEqual(manifest["report"]["id"], "ops")
        self.assertIsNone(manifest["report"]["category"])
        self.assertEqual(manifest["edition"]["highlights"], [{"label": "Incidents", "value": "0"}])
        self.assertEqual(manifest["html"], os.path.join(tmp, "report.html"))

    def test_optional_fields_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_manifest(tmp, edition={"id": "e1"})
            edition = load_manifest(path)["edition"]
        self.assertEqual(edition, {"id": "e1", "title": "e1", "period": None, "highlights": []})

    def test_invalid_manifests_are_rejected(self):
        cases = {
            "path traversal": {"edition": {"id": "../escape"}},
            "upper case slug": {"report": {"id": "Ops", "title": "t", "summary": "s"}},
            "blank title": {"report": {"id": "ops", "title": " ", "summary": "s"}},
            "period not object": {"edition": {"id": "e", "period": "Q3"}},
            "too many highlights": {
                "edition": {"id": "e", "highlights": [{"label": "a", "value": "b"}] * 7}
            },
            "highlight without value": {"edition": {"id": "e", "highlights": [{"label": "a"}]}},
            "missing file": {"files": {"html": "missing.html", "payload": "payload.json"}},
        }
        for name, override in cases.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(CatalogError):
                    load_manifest(write_manifest(tmp, **override))


class TestCatalog(unittest.TestCase):
    def test_missing_catalog_is_empty_and_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalog = load_catalog(tmp)
            self.assertEqual(catalog, {"schema": 1, "reports": []})
            save_catalog(tmp, catalog)
            self.assertEqual(load_catalog(tmp), catalog)
            self.assertFalse(os.path.exists(os.path.join(tmp, "catalog.json.tmp")))

    def test_unknown_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "catalog.json"), "w", encoding="utf-8") as f:
                json.dump({"schema": 99, "reports": []}, f)
            with self.assertRaises(CatalogError):
                load_catalog(tmp)

    def test_editions_and_reports_are_ordered_newest_first(self):
        catalog = {"schema": 1, "reports": []}

        def manifest(report_id, edition_id):
            return {
                "report": {"id": report_id, "title": report_id, "summary": "s"},
                "edition": {
                    "id": edition_id,
                    "title": edition_id,
                    "period": None,
                    "highlights": [],
                },
            }

        add_edition(catalog, manifest("a", "one"), "2026-09-01T00:00:00+00:00")
        add_edition(catalog, manifest("b", "one"), "2026-09-02T00:00:00+00:00")
        add_edition(catalog, manifest("a", "two"), "2026-09-03T00:00:00+00:00")
        self.assertEqual([r["id"] for r in catalog["reports"]], ["a", "b"])
        self.assertEqual([e["id"] for e in catalog["reports"][0]["editions"]], ["two", "one"])
        record = add_edition(catalog, manifest("a", "two"), "2026-09-04T00:00:00+00:00")
        self.assertEqual(edition_count(catalog), 3)
        self.assertEqual(record["path"], "reports/a/two/")
        self.assertEqual(record["payload"], "reports/a/two/payload.json")
        self.assertIsNone(latest({"editions": []}))

    def test_publish_copies_edition_and_records_it(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as site:
            report_id, record = publish(site, write_manifest(src), "2026-10-05T12:00:00+00:00")
            folder = os.path.join(site, "reports", "ops", "2026-10-05")
            with open(os.path.join(folder, "index.html"), encoding="utf-8") as f:
                self.assertEqual(f.read(), "<html>report</html>")
            self.assertTrue(os.path.exists(os.path.join(folder, "payload.json")))
            catalog = load_catalog(site)
        self.assertEqual(report_id, "ops")
        self.assertEqual(record["published_at"], "2026-10-05T12:00:00+00:00")
        self.assertEqual(catalog["reports"][0]["title"], "Ops Review")

    def test_publish_rejects_naive_time_and_bad_payload(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as site:
            path = write_manifest(src)
            with self.assertRaises(CatalogError):
                publish(site, path, "2026-10-05T12:00:00")
            with open(os.path.join(src, "payload.json"), "w", encoding="utf-8") as f:
                f.write("not json")
            with self.assertRaises(ValueError):
                publish(site, path, "2026-10-05T12:00:00+00:00")
            self.assertFalse(os.path.exists(os.path.join(site, "catalog.json")))


if __name__ == "__main__":
    unittest.main()
