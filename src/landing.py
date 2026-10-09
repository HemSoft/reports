"""Factual report directory and edition archive built from catalog.json."""

import html
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from src.branding import BRAND_MARK
from src.catalog import edition_count, latest, load_catalog

ET = ZoneInfo("America/New_York")


def _e(value):
    return html.escape(str(value), quote=True)


def _when(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _date(iso):
    moment = _when(iso).astimezone(ET)
    return f'<time datetime="{moment.date().isoformat()}">{moment.strftime("%b %d, %Y")}</time>'


def _href(report, edition=None):
    return f"reports/{report['id']}/{edition['id']}/" if edition else f"reports/{report['id']}/"


def _report_row(report):
    created = min(report["editions"], key=lambda e: _when(e["published_at"]))
    return (
        f'<tr><th scope="row">{_e(report["title"])}</th>'
        f'<td><a href="{_href(report)}" aria-label="Open {_e(report["title"])}">Open report</a></td>'
        f"<td>{_date(created['published_at'])}</td></tr>"
    )


def _directory(series):
    rows = "".join(_report_row(report) for report in series)
    if not rows:
        rows = '<tr><td colspan="3" class="empty">No reports have been published yet.</td></tr>'
    return (
        '<table class="directory" aria-describedby="date-note">'
        '<caption class="sr-only">Available reports</caption>'
        '<colgroup><col class="name-col"><col class="link-col"><col class="date-col"></colgroup>'
        '<thead><tr><th scope="col">Name</th><th scope="col">Link</th>'
        f'<th scope="col">Date created</th></tr></thead><tbody>{rows}</tbody></table>'
    )


def _edition_row(report, edition):
    period = edition.get("period")
    period_text = (
        f'<span class="period">{_e(period["start"])} – {_e(period["end"])}</span>' if period else ""
    )
    return (
        f'<tr><th scope="row">{_e(report["title"])}</th>'
        f'<td><a href="{_href(report, edition)}">{_e(edition["title"])}</a>{period_text}</td>'
        f"<td>{_date(edition['published_at'])}</td>"
        f'<td><a href="{_href(report, edition)}payload.json" '
        f'aria-label="{_e(report["title"])}: {_e(edition["title"])} data (JSON)">JSON</a></td></tr>'
    )


def _archive(series, total):
    if not series:
        return ""
    rows = "".join(_edition_row(report, e) for report in series for e in report["editions"])
    word = "edition" if total == 1 else "editions"
    return (
        '<details class="archive" id="archive">'
        f"<summary>Archived editions <span>({total:,} {word})</span></summary>"
        '<div class="archive-scroll" role="region" aria-label="Archived editions" tabindex="0">'
        '<table class="archive-table"><caption class="sr-only">All published editions</caption>'
        '<thead><tr><th scope="col">Report</th><th scope="col">Edition</th>'
        '<th scope="col">Published</th><th scope="col">Data</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div></details>"
    )


def published_series(catalog):
    return [r for r in catalog["reports"] if r["editions"]]


def build_index(catalog):
    series = published_series(catalog)
    total = edition_count(catalog)
    return PAGE.format(
        mark=BRAND_MARK,
        reports=len(series),
        reports_word="report" if len(series) == 1 else "reports",
        editions=f"{total:,}",
        editions_word="edition" if total == 1 else "editions",
        directory=_directory(series),
        archive=_archive(series, total),
        style=STYLE,
    )


def build_redirect(report):
    target = f"{latest(report)['id']}/"
    title = _e(report["title"])
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
        f'<meta http-equiv="refresh" content="0; url={target}"><title>{title} | HemSoft Reports</title>'
        '<meta name="robots" content="noindex"><style>body{background:#0a0a0a;color:#f5f5f5;'
        "font:1rem system-ui,sans-serif;display:grid;place-items:center;min-height:100vh;margin:0}"
        "a{color:#d4af37}</style></head><body>"
        f'<p>Opening the latest edition of {title}: <a href="{target}">{target}</a></p></body></html>'
    )


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build_site(site_dir):
    """Rebuild the directory and each report's latest-edition redirect from catalog.json."""
    catalog = load_catalog(site_dir)
    _write(os.path.join(site_dir, "index.html"), build_index(catalog))
    for report in published_series(catalog):
        _write(
            os.path.join(site_dir, "reports", report["id"], "index.html"), build_redirect(report)
        )
    _write(os.path.join(site_dir, ".nojekyll"), "")
    return catalog


STYLE = """
:root{color-scheme:dark;--bg:#0a0a0a;--surface:#141414;--rule:#303030;--text:#f5f5f5;
--muted:#ababab;--accent:#d4af37;--sans:ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:400 1rem/1.5 var(--sans)}
::selection{background:var(--accent);color:var(--bg)}
a{color:var(--accent);text-underline-offset:.2em;text-decoration-thickness:1px}
a:hover{text-decoration-thickness:2px;color:#f6e08f}
:focus-visible{outline:2px solid var(--accent);outline-offset:4px}
.wrap{width:min(1080px,100% - 3rem);margin-inline:auto}
.skip{position:absolute;left:-999px;top:0;padding:.75rem 1rem;background:var(--accent);color:var(--bg)}
.skip:focus{left:1rem;top:1rem}
.topbar{border-bottom:1px solid var(--rule)}
.topbar .wrap{display:flex;align-items:center;justify-content:space-between;gap:1rem;min-height:72px}
.brand{display:flex;align-items:center;gap:.65rem;color:var(--text);font-weight:650;text-decoration:none}
.mark{width:32px;height:20px;color:var(--accent);flex-shrink:0}
.topbar nav{font-size:.875rem}
main{padding-block:2.5rem 3rem}
h1{font-size:2rem;line-height:1.2;letter-spacing:-.02em;margin:0 0 .5rem;font-weight:650}
.description{margin:0;color:var(--muted);max-width:70ch}
.count{margin:1.5rem 0 .75rem;font-size:.875rem;color:var(--muted);font-variant-numeric:tabular-nums}
table{width:100%;border-collapse:collapse;text-align:left}
.directory{table-layout:fixed;border-top:1px solid var(--rule)}
.name-col{width:50%}.link-col{width:26%}.date-col{width:24%}
th,td{padding:1rem 1.25rem;border-bottom:1px solid var(--rule);vertical-align:top;overflow-wrap:anywhere}
thead{background:var(--surface);color:var(--muted);font-size:.8125rem}
thead th{font-weight:600}
tbody th{font-weight:550}
tbody tr:hover{background:var(--surface)}
time{font-variant-numeric:tabular-nums}
.directory td a{display:inline-block;min-height:24px}
.note{font-size:.8125rem;color:var(--muted);margin:.75rem 0 0;max-width:75ch}
.empty{color:var(--muted);padding-block:2rem}
.archive{margin-top:2rem;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}
summary{padding:1rem .25rem;cursor:pointer;font-weight:600}
summary span{color:var(--muted);font-weight:400;font-size:.875rem}
summary:hover{color:var(--accent)}
.archive-scroll{overflow-x:auto;scrollbar-width:thin;scrollbar-color:var(--muted) var(--surface);margin-bottom:1rem}
.archive-table{min-width:640px;font-size:.875rem}
.archive-table td:nth-child(3){white-space:nowrap}
.period{display:block;margin-top:.25rem;font-size:.8125rem;color:var(--muted)}
footer{border-top:1px solid var(--rule);padding-block:1.25rem;color:var(--muted);font-size:.8125rem}
footer .wrap{display:flex;flex-wrap:wrap;gap:.5rem 1.5rem;justify-content:space-between}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media(max-width:600px){.wrap{width:calc(100% - 2rem)}
.topbar .wrap{min-height:64px}.topbar nav{font-size:.8125rem}
main{padding-block:1.75rem 2rem}h1{font-size:1.75rem}
.name-col{width:40%}.link-col{width:28%}.date-col{width:32%}
th,td{padding:.85rem .5rem}.directory{font-size:.875rem}
.directory td a{min-height:44px;display:flex;align-items:flex-start}
summary{min-height:44px}footer .wrap{flex-direction:column}}
@media print{:root{color-scheme:light;--bg:#fff;--surface:#f4f4f4;--rule:#ccc;--text:#000;--muted:#444;--accent:#000}
.topbar,.skip,footer{display:none}.wrap{width:100%}.archive-scroll{overflow:visible}}
"""

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HemSoft Reports</title>
<meta name="description" content="Available HemSoft reports, creation dates and archived editions.">
<meta name="theme-color" content="#0a0a0a">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 40'%3E%3Cg fill='%23d4af37'%3E%3Cpolygon points='63,1 3,25 15,25'/%3E%3Cpolygon points='63,1 17,32 28,32'/%3E%3Cpolygon points='63,1 31,39 41,39'/%3E%3C/g%3E%3C/svg%3E">
<link rel="alternate" type="application/json" href="catalog.json" title="Report catalog">
<style>{style}</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="topbar"><div class="wrap">
  <a class="brand" href="./" aria-label="HemSoft Reports, home">{mark}<span>HemSoft Reports</span></a>
  <nav aria-label="Site resources"><a href="catalog.json">Catalog JSON</a></nav>
</div></header>
<main class="wrap" id="main" tabindex="-1">
  <h1>Reports</h1>
  <p class="description">Available reports and their archived editions.</p>
  <p class="count">{reports} {reports_word} · {editions} {editions_word}</p>
  {directory}
  <p class="note" id="date-note">Date created is the first recorded publication of a report.
  Dates use Eastern time (America/New_York). Report links open the latest edition.</p>
  {archive}
</main>
<footer><div class="wrap"><span>HemSoft Developments</span>
  <a href="https://github.com/hemsoft-dev/reports">Source on GitHub</a>
</div></footer>
</body>
</html>
"""
