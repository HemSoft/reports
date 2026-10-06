"""Published report archive: a catalog.json index plus one folder per report edition.

Site layout (also the GitHub Pages root):

    catalog.json
    index.html                              landing page, rebuilt from the catalog
    reports/<report>/index.html             redirect to the latest edition
    reports/<report>/<edition>/index.html   the edition as published
    reports/<report>/<edition>/payload.json the data behind the edition

Any tool can publish by writing an edition manifest (see ``load_manifest``) and running
``python publish.py add <site> --manifest <file>``.
"""

import json
import os
import re
import shutil
from datetime import datetime, timezone

SCHEMA = 1
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_HIGHLIGHTS = 6
# An edition page sits at reports/<report>/<edition>/index.html, three levels below the root.
EDITION_HOME = "../../../"


class CatalogError(ValueError):
    """Invalid catalog or edition manifest."""


def _slug(value, field):
    if not isinstance(value, str) or not SLUG.match(value):
        raise CatalogError(f"{field} must be a lowercase slug (a-z, 0-9, hyphen), got {value!r}")
    return value


def _object(value, field, required=True):
    if value is None and not required:
        return {}
    if not isinstance(value, dict):
        raise CatalogError(f"{field} must be a JSON object")
    return value


def _text(mapping, key, field, required=True):
    value = mapping.get(key)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{field} must be a non-empty string")
    return value.strip()


def _period(edition):
    period = edition.get("period")
    if period is None:
        return None
    period = _object(period, "edition.period")
    return {
        "start": _text(period, "start", "edition.period.start"),
        "end": _text(period, "end", "edition.period.end"),
    }


def _highlights(edition):
    items = edition.get("highlights", [])
    if not isinstance(items, list) or len(items) > MAX_HIGHLIGHTS:
        raise CatalogError(f"edition.highlights must be a list of at most {MAX_HIGHLIGHTS} items")
    return [
        {
            "label": _text(_object(item, "highlight"), "label", "highlight.label"),
            "value": _text(item, "value", "highlight.value"),
        }
        for item in items
    ]


def _file(files, key, base):
    """Resolve a manifest file, which must sit in the manifest's folder or below it."""
    relative = _text(files, key, f"files.{key}")
    path = os.path.normpath(os.path.join(base, relative))
    try:
        inside = not os.path.isabs(relative) and os.path.commonpath([base, path]) == base
    except ValueError:  # Different drives on Windows.
        inside = False
    if not inside:
        raise CatalogError(f"files.{key} must be a path relative to the manifest: {relative}")
    if not os.path.isfile(path):
        raise CatalogError(f"files.{key} does not exist: {path}")
    return path


def load_manifest(path):
    """Read and validate an edition manifest.

    {
      "report":  {"id", "title", "summary", "category"?, "cadence"?},
      "edition": {"id", "title"?, "period"?: {"start", "end"}, "highlights"?: [{"label", "value"}]},
      "files":   {"html", "payload"}   # relative to the manifest
    }
    """
    with open(path, encoding="utf-8") as f:
        manifest = _object(json.load(f), "manifest")
    report = _object(manifest.get("report"), "report")
    edition = _object(manifest.get("edition"), "edition")
    files = _object(manifest.get("files"), "files")
    base = os.path.dirname(os.path.abspath(path))
    edition_id = _slug(edition.get("id"), "edition.id")
    return {
        "report": {
            "id": _slug(report.get("id"), "report.id"),
            "title": _text(report, "title", "report.title"),
            "summary": _text(report, "summary", "report.summary"),
            "category": _text(report, "category", "report.category", required=False),
            "cadence": _text(report, "cadence", "report.cadence", required=False),
        },
        "edition": {
            "id": edition_id,
            "title": _text(edition, "title", "edition.title", required=False) or edition_id,
            "period": _period(edition),
            "highlights": _highlights(edition),
        },
        "html": _file(files, "html", base),
        "payload": _file(files, "payload", base),
    }


def load_catalog(site_dir):
    path = os.path.join(site_dir, "catalog.json")
    if not os.path.exists(path):
        return {"schema": SCHEMA, "reports": []}
    with open(path, encoding="utf-8") as f:
        catalog = json.load(f)
    if not isinstance(catalog, dict) or catalog.get("schema") != SCHEMA:
        raise CatalogError(f"Unsupported catalog in {path}")
    _check_records(catalog)
    return catalog


def _check_records(catalog):
    """The index trusts these fields; anything else in the catalog is passed through."""
    reports = catalog.get("reports")
    if not isinstance(reports, list):
        raise CatalogError("catalog.reports must be a list")
    for report in reports:
        _slug(_object(report, "catalog report").get("id"), "catalog report id")
        _text(report, "title", "catalog report title")
        _text(report, "summary", "catalog report summary")
        editions = report.get("editions")
        if not isinstance(editions, list):
            raise CatalogError(f"catalog report {report['id']} must list its editions")
        for edition in editions:
            _slug(_object(edition, "catalog edition").get("id"), "catalog edition id")
            _text(edition, "title", "catalog edition title")
            _utc(_text(edition, "published_at", "catalog edition published_at"))
            if not isinstance(edition.get("highlights"), list):
                raise CatalogError(f"catalog edition {edition['id']} must list its highlights")


def _utc(timestamp):
    """Normalize to UTC so string order is chronological order."""
    try:
        moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CatalogError(f"Invalid timestamp: {timestamp}") from exc
    if moment.utcoffset() is None:
        raise CatalogError("published_at must include a timezone offset")
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def save_catalog(site_dir, catalog):
    """Write atomically so a failed run never leaves a half-written catalog."""
    path = os.path.join(site_dir, "catalog.json")
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def edition_count(catalog):
    return sum(len(report["editions"]) for report in catalog["reports"])


def latest(report):
    return report["editions"][0] if report["editions"] else None


def _order(catalog):
    for report in catalog["reports"]:
        report["editions"].sort(key=lambda e: (e["published_at"], e["id"]), reverse=True)
    catalog["reports"].sort(
        key=lambda r: (latest(r)["published_at"] if latest(r) else "", r["id"]), reverse=True
    )


def add_edition(catalog, manifest, published_at):
    """Record an edition; republishing the same edition id replaces it."""
    meta, edition = manifest["report"], manifest["edition"]
    report = next((r for r in catalog["reports"] if r["id"] == meta["id"]), None)
    if report is None:
        report = {"id": meta["id"], "editions": []}
        catalog["reports"].append(report)
    report.update({k: v for k, v in meta.items() if k != "id"})
    folder = f"reports/{meta['id']}/{edition['id']}/"
    record = dict(edition, published_at=published_at, path=folder, payload=f"{folder}payload.json")
    report["editions"] = [e for e in report["editions"] if e["id"] != edition["id"]] + [record]
    _order(catalog)
    return record


def publish(site_dir, manifest_path, published_at):
    """Copy an edition into the site and record it in catalog.json."""
    published_at = _utc(published_at)
    manifest = load_manifest(manifest_path)
    with open(manifest["payload"], encoding="utf-8") as f:
        json.load(f)  # A payload must be valid JSON before it is archived.
    catalog = load_catalog(site_dir)
    record = add_edition(catalog, manifest, published_at)
    target = os.path.join(site_dir, *record["path"].rstrip("/").split("/"))
    os.makedirs(target, exist_ok=True)
    shutil.copyfile(manifest["html"], os.path.join(target, "index.html"))
    shutil.copyfile(manifest["payload"], os.path.join(target, "payload.json"))
    save_catalog(site_dir, catalog)
    return manifest["report"]["id"], record
