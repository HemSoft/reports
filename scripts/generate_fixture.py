"""Generate the browser fixture from synthetic data without GitHub or caches."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def main():
    from report_fixture import load_report_fixture
    from src.analyzer import analyze_data
    from src.catalog import add_edition, save_catalog
    from src.generator import edition_manifest
    from src.landing import build_site
    from src.template import build_html_report

    output = ROOT / "test-results"
    output.mkdir(exist_ok=True)
    analysis = analyze_data(load_report_fixture())
    (output / "report.html").write_text(build_html_report(analysis), encoding="utf-8")
    (output / "metrics.json").write_text(json.dumps(analysis, indent=2), encoding="utf-8")

    # Exercise the directory with repeated editions, long names and actual local targets.
    site = output / "landing"
    site.mkdir(exist_ok=True)
    catalog = {"schema": 1, "reports": []}
    for edition_id, stamp in (
        ("2026-09-05", "2026-09-06T01:00:00Z"),
        ("2026-09-07", "2026-09-07T12:00:00Z"),
    ):
        manifest = edition_manifest(analysis)
        manifest["edition"]["id"] = edition_id
        manifest["edition"]["title"] = f"Snapshot {edition_id}"
        record = add_edition(catalog, manifest, stamp)
        folder = site / record["path"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "index.html").write_text(
            '<!DOCTYPE html><html lang="en"><title>Fixture edition</title>'
            f'<h1>Snapshot {edition_id}</h1><a href="../../../">All reports</a></html>',
            encoding="utf-8",
        )
        (folder / "payload.json").write_text(json.dumps(analysis), encoding="utf-8")
    manifest = json.loads((ROOT / "editions/dune-awakening/2026-10-05/manifest.json").read_text())
    record = add_edition(catalog, manifest, "2026-10-06T12:00:00Z")
    folder = site / record["path"]
    folder.mkdir(parents=True, exist_ok=True)
    source = ROOT / "editions/dune-awakening/2026-10-05"
    (folder / "index.html").write_bytes((source / "report.html").read_bytes())
    (folder / "payload.json").write_bytes((source / "payload.json").read_bytes())
    save_catalog(site, catalog)
    build_site(site)
    empty = output / "landing-empty"
    empty.mkdir(exist_ok=True)
    build_site(empty)


if __name__ == "__main__":
    main()
