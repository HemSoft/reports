import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from src.catalog import add_edition
from src.landing import (
    _short,
    build_index,
    build_redirect,
    build_site,
    map_domain,
    transit_map,
)


def manifest(report_id, edition_id, title="Report", highlights=(), period=None, **meta):
    return {
        "report": dict({"id": report_id, "title": title, "summary": f"{title} summary"}, **meta),
        "edition": {
            "id": edition_id,
            "title": f"Edition {edition_id}",
            "period": period,
            "highlights": [{"label": k, "value": v} for k, v in highlights],
        },
    }


def catalog_with(*entries):
    catalog = {"schema": 1, "reports": []}
    for report_id, edition_id, published, kwargs in entries:
        add_edition(catalog, manifest(report_id, edition_id, **kwargs), published)
    return catalog


class TestMapDomain(unittest.TestCase):
    def test_short_window_is_widened_and_long_window_is_capped(self):
        one = catalog_with(("a", "e1", "2026-10-05T12:00:00+00:00", {}))["reports"]
        start, end = map_domain(one)
        self.assertEqual((end - start).days, 28)
        many = catalog_with(
            ("a", "old", "2024-01-01T00:00:00+00:00", {}),
            ("a", "new", "2026-10-05T00:00:00+00:00", {}),
        )["reports"]
        start, end = map_domain(many)
        self.assertEqual((end - start).days, 365)
        self.assertEqual(start, datetime(2025, 10, 5, tzinfo=timezone.utc))

    def test_editions_older_than_window_stay_off_the_map(self):
        series = catalog_with(
            ("a", "old", "2024-01-01T00:00:00+00:00", {}),
            ("a", "new", "2026-10-05T00:00:00+00:00", {}),
            ("b", "ancient", "2023-01-01T00:00:00+00:00", {}),
        )["reports"]
        svg = transit_map(series)
        self.assertIn('href="reports/a/new/"', svg)
        self.assertNotIn('href="reports/a/old/"', svg)
        # A series with nothing recent still keeps its newest stop so its line is drawn.
        self.assertIn('href="reports/b/ancient/"', svg)
        self.assertIn("Jan 2026", svg)

    def test_empty_map(self):
        self.assertIn("map-empty", transit_map([]))

    def test_long_titles_are_shortened(self):
        self.assertEqual(_short("abc"), "abc")
        self.assertEqual(len(_short("x" * 50)), 30)


class TestIndex(unittest.TestCase):
    def test_index_lists_every_series_and_edition(self):
        entries = [
            (
                "productivity",
                f"2026-{month:02d}-01",
                f"2026-{month:02d}-01T12:00:00+00:00",
                {
                    "title": "Engineering <Audit>",
                    "highlights": [("Commits", "1,394")],
                    "period": {"start": "Jun 13, 2026", "end": "Sep 05, 2026"},
                    "category": "Engineering",
                    "cadence": "Weekly",
                },
            )
            for month in range(1, 9)
        ]
        entries.append(("ops", "w1", "2026-09-15T12:00:00+00:00", {"title": "Ops"}))
        page = build_index(catalog_with(*entries))
        self.assertIn("2 reports, 9 editions so far.", page)
        self.assertIn("Engineering &lt;Audit&gt;", page)
        self.assertNotIn("<Audit>", page)
        self.assertIn('href="reports/ops/w1/"', page)  # newest edition overall
        self.assertIn('href="reports/productivity/2026-08-01/payload.json"', page)
        self.assertIn("All 8 editions", page)
        self.assertIn("Jun 13, 2026 – Sep 05, 2026", page)
        self.assertIn('<span class="tag">Engineering</span>', page)
        self.assertIn("Commits: 1,394", page)

    def test_single_edition_wording(self):
        page = build_index(catalog_with(("ops", "w1", "2026-09-15T12:00:00+00:00", {})))
        self.assertIn("1 report, 1 edition so far.", page)
        self.assertIn('class="tag live">1 edition<', page)
        self.assertIn("Published edition.", page)
        self.assertNotIn("All 1 editions", page)

    def test_empty_catalog(self):
        page = build_index({"schema": 1, "reports": [{"id": "x", "editions": []}]})
        self.assertIn("0 reports, 0 editions so far.", page)
        self.assertIn("The catalog is empty.", page)
        self.assertIn('href="#reports"', page)
        self.assertIn("None yet", page)

    def test_redirect_points_at_latest_edition(self):
        report = catalog_with(
            ("ops", "w1", "2026-09-15T12:00:00+00:00", {}),
            ("ops", "w2", "2026-09-22T12:00:00+00:00", {}),
        )["reports"][0]
        page = build_redirect(report)
        self.assertIn('content="0; url=w2/"', page)
        self.assertIn('href="w2/"', page)


class TestBuildSite(unittest.TestCase):
    def test_build_writes_index_redirects_and_nojekyll(self):
        catalog = catalog_with(("ops", "w1", "2026-09-15T12:00:00+00:00", {}))
        with tempfile.TemporaryDirectory() as site:
            with open(os.path.join(site, "catalog.json"), "w", encoding="utf-8") as f:
                json.dump(catalog, f)
            build_site(site)
            for path in ("index.html", ".nojekyll", os.path.join("reports", "ops", "index.html")):
                self.assertTrue(os.path.exists(os.path.join(site, path)), path)


if __name__ == "__main__":
    unittest.main()
