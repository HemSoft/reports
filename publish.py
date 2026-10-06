#!/usr/bin/env python3
"""
HemSoft Reports publishing CLI

add      Add an edition (manifest + report HTML + JSON payload) to the site and catalog.json.
sync     Import checked-in static editions without changing their first publication dates.
build    Rebuild index.html and the latest-edition redirects from catalog.json.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.catalog import CatalogError, load_catalog, load_manifest, publish
from src.landing import build_site


def sync_editions(site_dir, editions_dir):
    """Import checked-in static editions, preserving their first publication date."""
    source = Path(editions_dir)
    if not source.is_dir():
        raise CatalogError(f"Static editions folder does not exist: {source}")
    manifests = sorted(source.glob("*/*/manifest.json"))
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for path in manifests:
        manifest = load_manifest(path)
        report = next(
            (r for r in load_catalog(site_dir)["reports"] if r["id"] == manifest["report"]["id"]),
            {"editions": []},
        )
        existing = next(
            (e for e in report["editions"] if e["id"] == manifest["edition"]["id"]), None
        )
        published_at = existing["published_at"] if existing else stamp
        publish(site_dir, path, published_at)
    return len(manifests)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Publish reports and build the HemSoft Reports site."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    pub = commands.add_parser("add", help="Add an edition to the site")
    pub.add_argument("site_dir", help="Site folder (the published branch checkout)")
    pub.add_argument("--manifest", required=True, help="Edition manifest JSON")
    pub.add_argument(
        "--published-at",
        default=None,
        help="ISO timestamp with offset to record (default: now, UTC)",
    )
    build = commands.add_parser("build", help="Rebuild index.html from catalog.json")
    build.add_argument("site_dir", help="Site folder (the published branch checkout)")
    sync = commands.add_parser("sync", help="Import checked-in static editions")
    sync.add_argument("site_dir", help="Site folder (the published branch checkout)")
    sync.add_argument("--editions", default="editions", help="Static editions folder")
    args = parser.parse_args(argv)

    try:
        if args.command == "add":
            stamp = args.published_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
            report_id, record = publish(args.site_dir, args.manifest, stamp)
            print(f"Published {report_id} edition {record['id']} at {record['path']}")
        elif args.command == "sync":
            count = sync_editions(args.site_dir, args.editions)
            print(f"Synced {count} static edition(s) to {args.site_dir}")
        else:
            catalog = build_site(args.site_dir)
            print(f"Built index for {len(catalog['reports'])} report(s) in {args.site_dir}")
    except (CatalogError, OSError, ValueError) as exc:
        print(f"{args.command} failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
