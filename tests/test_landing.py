import json
import os
import tempfile
import unittest
from html.parser import HTMLParser

from src.catalog import add_edition
from src.landing import build_index, build_redirect, build_site


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


class DirectoryParser(HTMLParser):
    """Read the report table independently of the generator's string formatting."""

    def __init__(self, page):
        super().__init__()
        self.in_directory = False
        self.rows = []
        self.cell = None
        self.links = []
        self.dates = []
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table" and attrs.get("class") == "directory":
            self.in_directory = True
        if not self.in_directory:
            return
        if tag == "tr":
            self.rows.append([])
        if tag in ("th", "td"):
            self.cell = ""
        if tag == "a":
            self.links.append(attrs["href"])
        if tag == "time":
            self.dates.append(attrs["datetime"])

    def handle_data(self, data):
        if self.in_directory and self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if self.in_directory and tag in ("th", "td"):
            self.rows[-1].append(self.cell)
            self.cell = None
        if tag == "table":
            self.in_directory = False


class TestIndex(unittest.TestCase):
    def test_directory_lists_each_report_once_with_first_publication_date(self):
        entries = [
            (
                "productivity",
                f"2026-{month:02d}-01",
                f"2026-{month:02d}-01T12:00:00+00:00",
                {"title": "Engineering <Audit>"},
            )
            for month in range(1, 9)
        ]
        entries.append(("ops", "w1", "2026-09-15T12:00:00+00:00", {"title": "Ops"}))
        page = build_index(catalog_with(*entries))
        directory = DirectoryParser(page)
        self.assertEqual(directory.rows[0], ["Name", "Link", "Date created"])
        self.assertEqual(
            directory.rows[1:],
            [
                ["Ops", "Open report", "Sep 15, 2026"],
                ["Engineering <Audit>", "Open report", "Jan 01, 2026"],
            ],
        )
        self.assertEqual(directory.links, ["reports/ops/", "reports/productivity/"])
        self.assertEqual(directory.dates, ["2026-09-15", "2026-01-01"])
        self.assertIn("2 reports · 9 editions", page)
        self.assertIn("Engineering &lt;Audit&gt;", page)
        self.assertNotIn("<Audit>", page)
        for month in range(1, 9):
            link = f"reports/productivity/2026-{month:02d}-01/"
            self.assertIn(f'href="{link}"', page)
            self.assertIn(f'href="{link}payload.json"', page)

    def test_creation_date_compares_instants_and_uses_eastern_timezone(self):
        catalog = catalog_with(
            ("ops", "e1", "2026-01-01T01:00:00+00:00", {}),
            ("ops", "e2", "2025-12-31T23:00:00-05:00", {}),
            ("ops", "e3", "2026-07-01T03:00:00Z", {}),
        )
        catalog["reports"][0]["editions"].reverse()  # Creation must not depend on list order.
        page = build_index(catalog)
        self.assertEqual(DirectoryParser(page).dates, ["2025-12-31"])
        self.assertIn('datetime="2026-06-30">Jun 30, 2026', page)
        self.assertIn("first recorded publication", page)
        self.assertIn("America/New_York", page)

    def test_archive_escapes_titles_periods_and_accessible_labels(self):
        catalog = catalog_with(
            (
                "ops",
                "e1",
                "2026-10-05T12:00:00Z",
                {
                    "title": 'Ops "<Review>" & data',
                    "period": {"start": "<start>", "end": '"end"'},
                },
            )
        )
        catalog["reports"][0]["editions"][0]["title"] = '<img src=x onerror="bad">'
        page = build_index(catalog)
        self.assertNotIn("<img", page)
        self.assertNotIn("<Review>", page)
        self.assertIn("&lt;start&gt; – &quot;end&quot;", page)
        self.assertIn('aria-label="Open Ops &quot;&lt;Review&gt;&quot; &amp; data"', page)
        self.assertIn("&lt;img src=x onerror=&quot;bad&quot;&gt;", page)

    def test_single_edition_and_removed_decorative_content(self):
        page = build_index(catalog_with(("ops", "w1", "2026-09-15T12:00:00+00:00", {})))
        self.assertIn("1 report · 1 edition", page)
        self.assertIn("(1 edition)", page)
        self.assertIn('<details class="archive"', page)
        for removed in ("transit", "on one map", "<script", "fonts.googleapis", "linear-gradient"):
            self.assertNotIn(removed, page)

    def test_empty_catalog_and_unpublished_series(self):
        for reports in ([], [{"id": "x", "editions": []}]):
            with self.subTest(reports=reports):
                page = build_index({"schema": 1, "reports": reports})
                self.assertIn("0 reports · 0 editions", page)
                self.assertIn("No reports have been published yet.", page)
                self.assertEqual(DirectoryParser(page).links, [])
                self.assertNotIn('<details class="archive"', page)

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
