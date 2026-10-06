"""HemSoft Reports index: a landing page built from catalog.json.

Every report series is a line on a transit map and every published edition is a stop,
placed on the day it was published. Below the map, each series lists its editions.
"""

import html
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.catalog import edition_count, latest, load_catalog

ET = ZoneInfo("America/New_York")
LINE_COLORS = (
    "#d4af37",
    "#f2efe6",
    "#c9773f",
    "#6f8fb0",
    "#8fa37a",
    "#c98b9b",
    "#5fa8a0",
    "#e2c290",
)
MAP_WIDTH = 1000
ORIGIN_X = 30
LABEL_ROOM = 210
MAP_TOP = 44
MAP_ROW = 72
LANE = 7
STUB = 10
WINDOW_DAYS = 365
MIN_SPAN_DAYS = 28
VISIBLE_EDITIONS = 6

BRAND_MARK = """<svg class="mark" viewBox="0 0 64 40" aria-hidden="true" focusable="false">
  <defs><linearGradient id="gold" x1="0" y1="1" x2="1" y2="0">
    <stop offset="0" stop-color="#8b6914"/><stop offset=".55" stop-color="#d4af37"/>
    <stop offset="1" stop-color="#f6e08f"/></linearGradient></defs>
  <polygon fill="url(#gold)" points="63,1 3,25 15,25"/>
  <polygon fill="url(#gold)" points="63,1 17,32 28,32"/>
  <polygon fill="url(#gold)" points="63,1 31,39 41,39"/>
</svg>"""
FOOTER_MARK = re.sub(r"<defs>.*?</defs>", "", BRAND_MARK, flags=re.S).replace(
    'fill="url(#gold)"', 'fill="currentColor"'
)


def _e(value):
    return html.escape(str(value), quote=True)


def _when(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _day(iso):
    return _when(iso).astimezone(ET).strftime("%b %d, %Y")


def _short(text, limit=30):
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _href(report, edition=None):
    return f"reports/{report['id']}/{edition['id']}/" if edition else f"reports/{report['id']}/"


def _color(index):
    return LINE_COLORS[index % len(LINE_COLORS)]


def _period(edition):
    period = edition.get("period")
    return f"{period['start']} – {period['end']}" if period else ""


def _highlights_text(edition):
    return " · ".join(f"{h['label']}: {h['value']}" for h in edition["highlights"])


def map_domain(series):
    """Time window for the map: the last year of editions, at least four weeks wide."""
    times = [_when(e["published_at"]) for r in series for e in r["editions"]]
    end = max(times)
    start = max(min(times), end - timedelta(days=WINDOW_DAYS))
    return min(start, end - timedelta(days=MIN_SPAN_DAYS)), end


def _rows(count):
    ys = [MAP_TOP + i * MAP_ROW for i in range(count)]
    trunk = MAP_TOP + (count - 1) * MAP_ROW / 2
    lanes = [trunk + (i - (count - 1) / 2) * LANE for i in range(count)]
    return ys, lanes


def _scale(start, end, reach):
    x0 = ORIGIN_X + 24 + reach + STUB
    x1 = MAP_WIDTH - LABEL_ROOM
    span = (end - start).total_seconds()

    def x(iso):
        moment = max(_when(iso), start)
        return x0 + (moment - start).total_seconds() / span * (x1 - x0)

    return x


def _axis(start, end, x, height):
    ticks = []
    month = datetime(start.year, start.month, 1, tzinfo=start.tzinfo)
    while month <= end:
        if month >= start:
            label = month.strftime("%b %Y" if month.month == 1 or not ticks else "%b")
            pos = x(month.isoformat())
            ticks.append(
                f'<line class="tick" x1="{pos:.1f}" x2="{pos:.1f}" y1="{MAP_TOP - 28}" '
                f'y2="{height - 36}"/><text class="axis" x="{pos:.1f}" y="{height - 16}">{label}</text>'
            )
        month = (month + timedelta(days=32)).replace(day=1)
    return "".join(ticks)


def _station(report, edition, index, x, y, lead):
    color = _color(index)
    return (
        f'<a href="{_href(report, edition)}" tabindex="-1">'
        f'<circle class="station{" lead" if lead else ""}" cx="{x:.1f}" cy="{y:.1f}" '
        f'r="{8 if lead else 4.5}" data-report="{_e(report["title"])}" '
        f'data-edition="{_e(edition["title"])}" data-date="{_day(edition["published_at"])}" '
        f'data-highlights="{_e(_highlights_text(edition))}" data-color="{color}">'
        f"<title>{_e(report['title'])}: {_e(edition['title'])}</title></circle></a>"
    )


def _line(index, report, y, lane, x, start):
    editions = [e for e in report["editions"] if _when(e["published_at"]) >= start]
    editions = editions or report["editions"][:1]
    first, last = x(editions[-1]["published_at"]), x(editions[0]["published_at"])
    rise = abs(y - lane)
    track = (
        f"M{ORIGIN_X} {lane:.1f}H{first - rise - STUB:.1f}L{first - STUB:.1f} {y:.1f}H{last:.1f}"
    )
    stations = "".join(
        _station(report, e, index, x(e["published_at"]), y, e is editions[0])
        for e in reversed(editions)
    )
    return (
        f'<g class="line" data-line="{_e(report["id"])}" style="--c:{_color(index)};--i:{index}">'
        f'<path class="track" pathLength="1" d="{track}"/>{stations}'
        f'<text class="line-label" x="{last + 16:.1f}" y="{y + 4:.1f}">{_e(_short(report["title"]))}</text></g>'
    )


def transit_map(series):
    if not series:
        return '<p class="map-empty">No reports have been published yet. The first edition starts the first line.</p>'
    ys, lanes = _rows(len(series))
    start, end = map_domain(series)
    x = _scale(start, end, max(abs(y - lane) for y, lane in zip(ys, lanes)))
    height = ys[-1] + 64
    lines = "".join(
        _line(i, report, ys[i], lanes[i], x, start)
        for i, report in reversed(list(enumerate(series)))
    )
    top, bottom = lanes[0] - 10, lanes[-1] + 10
    origin = (
        f'<rect class="origin" x="{ORIGIN_X - 10}" y="{top:.1f}" width="20" '
        f'height="{bottom - top:.1f}" rx="10"/>'
        f'<text class="origin-label" x="{ORIGIN_X}" y="{bottom + 22:.1f}">Index</text>'
    )
    return (
        f'<svg class="map" viewBox="0 0 {MAP_WIDTH} {height:.0f}" role="img" '
        'aria-labelledby="map-title map-desc"><title id="map-title">Published HemSoft reports over time'
        '</title><desc id="map-desc">Each line is a report series starting from this index. Each stop '
        "is an edition, placed on its publication date; the large ring is the latest edition.</desc>"
        f"{_axis(start, end, x, height)}{lines}{origin}</svg>"
    )


def _legend(series):
    items = "".join(
        f'<li><button type="button" class="legend-item" data-line="{_e(r["id"])}" aria-pressed="false" '
        f'style="--c:{_color(i)}"><span class="swatch"></span><span class="legend-name">{_e(r["title"])}</span>'
        f'<span class="legend-meta">{len(r["editions"])} edition{"s" if len(r["editions"]) != 1 else ""}</span>'
        "</button></li>"
        for i, r in enumerate(series)
    )
    return f'<ul class="legend" aria-label="Report series on the map">{items}</ul>'


def _card(series):
    if not series:
        return ""
    report, edition = series[0], latest(series[0])
    return (
        '<aside class="map-card" id="map-card" aria-live="polite">'
        f'<p class="card-kicker" data-field="date">Latest · {_day(edition["published_at"])}</p>'
        f'<p class="card-title" data-field="title">{_e(edition["title"])}</p>'
        f'<p class="card-body" data-field="body">{_e(_highlights_text(edition)) or "Published edition."}</p>'
        f'<p class="card-chip" data-field="chip" style="--c:{_color(0)}">'
        f'<span class="swatch"></span><span data-field="report">{_e(report["title"])}</span></p></aside>'
    )


def _stats(catalog, series):
    editions = [e for r in series for e in r["editions"]]
    newest = max((e["published_at"] for e in editions), default=None)
    oldest = min((e["published_at"] for e in editions), default=None)
    stats = [
        ("Reports", f"{len(series)}"),
        ("Editions published", f"{edition_count(catalog):,}"),
        ("Latest edition", _day(newest) if newest else "None yet"),
        ("Archive since", _day(oldest) if oldest else "None yet"),
    ]
    cells = "".join(
        f'<div class="stat"><dt>{label}</dt><dd>{value}</dd></div>' for label, value in stats
    )
    return f'<dl class="stats">{cells}</dl>'


def _edition_row(report, edition):
    highlights = "".join(
        f'<span class="hl"><span>{_e(h["label"])}</span> {_e(h["value"])}</span>'
        for h in edition["highlights"]
    )
    period = _period(edition)
    return (
        f'<li class="edition"><a class="edition-link" href="{_href(report, edition)}">'
        f'<span class="ed-date">{_day(edition["published_at"])}</span>'
        f'<span class="ed-main"><span class="ed-title">{_e(edition["title"])}</span>'
        f"{f'<span class=ed-period>{_e(period)}</span>' if period else ''}</span>"
        f'<span class="ed-hl">{highlights}</span><span class="arrow" aria-hidden="true">→</span></a>'
        f'<a class="ed-json" href="{_href(report, edition)}payload.json" '
        f'aria-label="{_e(edition["title"])} payload (JSON)">JSON</a></li>'
    )


def _series(index, report):
    editions = report["editions"]
    first, rest = editions[:VISIBLE_EDITIONS], editions[VISIBLE_EDITIONS:]
    more = (
        f'<details class="more"><summary>All {len(editions)} editions</summary>'
        f'<ol class="editions">{"".join(_edition_row(report, e) for e in rest)}</ol></details>'
        if rest
        else ""
    )
    tags = [report.get("category"), report.get("cadence")]
    tags = "".join(f'<span class="tag">{_e(t)}</span>' for t in tags if t)
    count = f"{len(editions)} edition{'s' if len(editions) != 1 else ''}"
    return (
        f'<article class="series" id="report-{_e(report["id"])}" style="--c:{_color(index)}">'
        f'<header class="series-head"><span class="series-no" aria-hidden="true">{index + 1:02d}</span>'
        f'<div><h3><a href="{_href(report)}">{_e(report["title"])}</a></h3>'
        f"<p>{_e(report['summary'])}</p>"
        f'<p class="tags"><span class="tag live">{count}</span>{tags}'
        f'<span class="tag">Since {_day(editions[-1]["published_at"])}</span></p></div>'
        f'<a class="pill" href="{_href(report, editions[0])}">Open latest <span class="arrow" aria-hidden="true">→</span></a>'
        f'</header><ol class="editions">{"".join(_edition_row(report, e) for e in first)}</ol>{more}</article>'
    )


def _directory(series):
    if not series:
        return '<p class="map-empty">The catalog is empty.</p>'
    return "".join(_series(i, r) for i, r in enumerate(series))


STEPS = (
    (
        "Generate",
        "Any tool renders its report as one HTML file and writes the data behind it as JSON.",
    ),
    (
        "Describe",
        "A small manifest names the report and the edition, with its period and up to six highlights.",
    ),
    (
        "Publish",
        "<code>publish.py add</code> files the edition under <code>reports/&lt;report&gt;/&lt;edition&gt;/</code> "
        "and records it in <code>catalog.json</code>.",
    ),
    (
        "Deploy",
        "This index is rebuilt from the catalog, committed to the <code>published</code> branch and "
        "served by GitHub Pages.",
    ),
)

MANIFEST_SAMPLE = """{
  <span class="k">"report"</span>: { <span class="k">"id"</span>: <span class="s">"productivity"</span>, <span class="k">"title"</span>: <span class="s">"…"</span>, <span class="k">"summary"</span>: <span class="s">"…"</span> },
  <span class="k">"edition"</span>: {
    <span class="k">"id"</span>: <span class="s">"2026-10-05"</span>,
    <span class="k">"period"</span>: { <span class="k">"start"</span>: <span class="s">"Jul 14, 2026"</span>, <span class="k">"end"</span>: <span class="s">"Oct 05, 2026"</span> },
    <span class="k">"highlights"</span>: [ { <span class="k">"label"</span>: <span class="s">"Commits"</span>, <span class="k">"value"</span>: <span class="s">"1,394"</span> } ]
  },
  <span class="k">"files"</span>: { <span class="k">"html"</span>: <span class="s">"report.html"</span>, <span class="k">"payload"</span>: <span class="s">"payload.json"</span> }
}"""


def _steps():
    return "".join(
        f'<li class="step"><span class="stop" aria-hidden="true"></span><h3>{title}</h3><p>{body}</p></li>'
        for title, body in STEPS
    )


def published_series(catalog):
    return [r for r in catalog["reports"] if r["editions"]]


def build_index(catalog):
    series = published_series(catalog)
    newest = latest(series[0]) if series else None
    total = edition_count(catalog)
    return PAGE.format(
        mark=BRAND_MARK,
        footer_mark=FOOTER_MARK,
        latest=_href(series[0], newest) if newest else "#reports",
        reports=len(series),
        reports_word="report" if len(series) == 1 else "reports",
        editions=f"{total:,}",
        editions_word="edition" if total == 1 else "editions",
        legend=_legend(series),
        card=_card(series),
        map=transit_map(series),
        stats=_stats(catalog, series),
        directory=_directory(series),
        steps=_steps(),
        manifest=MANIFEST_SAMPLE,
        style=STYLE,
        script=SCRIPT,
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
    """Rebuild the index and each report's latest-edition redirect from catalog.json."""
    catalog = load_catalog(site_dir)
    _write(os.path.join(site_dir, "index.html"), build_index(catalog))
    for report in published_series(catalog):
        _write(
            os.path.join(site_dir, "reports", report["id"], "index.html"), build_redirect(report)
        )
    _write(os.path.join(site_dir, ".nojekyll"), "")
    return catalog


STYLE = """
:root{--ink:#0a0a0a;--panel:#121212;--rule:#2a2a2a;--text:#f5f5f5;--muted:#a3a3a3;
--gold:#d4af37;--gold-deep:#b8860b;--gold-pale:#f6e08f;
--sans:'Geist',ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif;
--mono:'Geist Mono',ui-monospace,'Cascadia Mono',Consolas,monospace;--wrap:min(1240px,100% - 3rem)}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--ink);color:var(--text);font:400 1.0625rem/1.6 var(--sans);
-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:inherit}
code{font:500 .85em var(--mono);color:var(--gold-pale)}
:focus-visible{outline:2px solid var(--gold);outline-offset:3px;border-radius:4px}
.skip{position:absolute;left:-999px;top:0;background:var(--gold);color:var(--ink);padding:.6rem 1rem;z-index:10}
.skip:focus{left:1rem;top:1rem}
.wrap{width:var(--wrap);margin-inline:auto}
.topbar{position:sticky;top:0;z-index:5;background:rgba(10,10,10,.82);backdrop-filter:blur(14px);
border-bottom:1px solid var(--rule)}
.topbar .wrap{display:flex;align-items:center;gap:2rem;height:68px}
.brand{display:flex;align-items:center;gap:.75rem;text-decoration:none;font-weight:700;letter-spacing:-.01em}
.brand .mark{width:40px;height:25px}
.brand small{display:block;font:500 .625rem/1 var(--sans);letter-spacing:.32em;color:var(--gold);text-transform:uppercase;margin-top:3px}
.nav{display:flex;gap:1.75rem;margin-left:auto;font-size:.9375rem}
.nav a{text-decoration:none;color:var(--muted);transition:color .2s}
.nav a:hover{color:var(--text)}
.pill{display:inline-flex;align-items:center;gap:.5rem;padding:.7rem 1.25rem;border-radius:999px;white-space:nowrap;
background:var(--gold);color:var(--ink);font-weight:650;text-decoration:none;font-size:.9375rem;
transition:transform .2s,box-shadow .2s}
.pill:hover{transform:translateY(-1px);box-shadow:0 10px 30px -8px rgba(212,175,55,.55)}
.pill .arrow{transition:transform .2s}
.pill:hover .arrow{transform:translateX(3px)}
.hero{position:relative;padding:clamp(3.5rem,8vw,6.5rem) 0 4rem;overflow:hidden}
.hero::before{content:"";position:absolute;inset:-30% -10% auto 40%;height:620px;pointer-events:none;
background:radial-gradient(closest-side,rgba(212,175,55,.13),transparent);filter:blur(10px)}
.eyebrow{font:500 .8125rem/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--gold);
display:flex;align-items:center;gap:.75rem;margin:0 0 1.5rem}
.eyebrow::before{content:"";width:2.5rem;height:2px;background:var(--gold)}
h1{font-size:clamp(3.1rem,8.4vw,7rem);line-height:.92;letter-spacing:-.055em;font-weight:800;margin:0}
h1 em{font-style:normal;background:linear-gradient(100deg,var(--gold-pale),var(--gold) 45%,var(--gold-deep));
-webkit-background-clip:text;background-clip:text;color:transparent}
.lede{max-width:40rem;font-size:clamp(1.0625rem,1.6vw,1.25rem);color:#d4d4d4;margin:2rem 0 0}
.lede strong{color:var(--text);font-weight:600}
.atlas{display:grid;grid-template-columns:260px minmax(0,1fr);gap:clamp(1.5rem,4vw,3.5rem);margin-top:4rem;align-items:start}
.legend-title{font-weight:700;font-size:.875rem;margin:0 0 .6rem;padding-bottom:.6rem;border-bottom:3px solid var(--text)}
.legend{list-style:none;margin:0 0 1.5rem;padding:0}
.legend li{border-bottom:1px solid var(--rule)}
.legend-item{all:unset;box-sizing:border-box;width:100%;display:grid;grid-template-columns:22px 1fr;
column-gap:.6rem;padding:.7rem .25rem;cursor:pointer;border-radius:6px;transition:background .2s}
.legend-item:hover,.legend-item[aria-pressed=true]{background:#171717}
.legend-item:focus-visible{outline:2px solid var(--gold)}
.swatch{width:22px;height:6px;border-radius:3px;background:var(--c);align-self:center}
.legend-name{font-weight:650;font-size:.9375rem;overflow-wrap:anywhere}
.legend-meta{grid-column:2;font-size:.8125rem;color:var(--muted)}
.map-card{background:linear-gradient(160deg,#1a1608,#121212 55%);border:1px solid rgba(212,175,55,.35);
border-radius:10px;padding:1.1rem 1.15rem;box-shadow:0 20px 50px -25px rgba(212,175,55,.35)}
.map-card p{margin:0}
.card-kicker{font:500 .75rem/1.2 var(--mono);color:var(--gold);letter-spacing:.06em;text-transform:uppercase}
.card-title{font-weight:700;font-size:1.0625rem;margin-top:.45rem!important;line-height:1.3}
.card-body{font-size:.875rem;color:#cfcfcf;margin-top:.4rem!important;line-height:1.5}
.card-chip{display:flex;align-items:center;gap:.5rem;font-size:.8125rem;font-weight:650;margin-top:.8rem!important}
.card-chip .swatch{width:16px;height:5px}
.map-frame{overflow-x:auto;scrollbar-width:thin;scrollbar-color:#333 transparent}
.map{display:block;width:100%;min-width:680px;height:auto;overflow:visible}
.map .tick{stroke:#1d1d1d;stroke-width:1}
.map .axis{fill:var(--muted);font:500 11px var(--mono);text-anchor:middle}
.map .track{fill:none;stroke:var(--c);stroke-width:8;stroke-linecap:round;stroke-linejoin:round;
stroke-dasharray:1;stroke-dashoffset:1;animation:draw 1.5s cubic-bezier(.6,.05,.25,1) forwards;
animation-delay:calc(var(--i) * 140ms + 150ms)}
.map .origin{fill:var(--ink);stroke:var(--text);stroke-width:3.5}
.map .origin-label{fill:var(--gold);font:600 10px var(--mono);letter-spacing:.12em;text-transform:uppercase;text-anchor:middle}
.map .station{fill:var(--ink);stroke:var(--c);stroke-width:3;cursor:pointer;opacity:0;
transform-box:fill-box;transform-origin:center;animation:pop .45s cubic-bezier(.3,1.6,.5,1) forwards;
animation-delay:calc(1.2s + var(--i) * 120ms);transition:stroke-width .15s}
.map .station.lead{stroke:var(--text);stroke-width:3.5}
.map .station:hover,.map .station.is-active{stroke-width:5;fill:var(--c)}
.map .line-label{fill:var(--text);font:650 13px var(--sans);opacity:0;animation:fade .5s ease forwards;
animation-delay:calc(1.4s + var(--i) * 120ms)}
.map .line{transition:opacity .25s}
.map[data-focus] .line{opacity:.12}
.map[data-focus] .line.is-focus{opacity:1}
@keyframes draw{to{stroke-dashoffset:0}}
@keyframes pop{from{opacity:0;transform:scale(.2)}to{opacity:1;transform:scale(1)}}
@keyframes fade{to{opacity:1}}
.map-empty{color:var(--muted);border:1px dashed var(--rule);border-radius:10px;padding:3rem;text-align:center}
section.band{border-top:3px solid var(--text);padding:clamp(3.5rem,7vw,5.5rem) 0}
h2{font-size:clamp(2rem,4.2vw,3.25rem);letter-spacing:-.04em;line-height:1;margin:0 0 .75rem;font-weight:800}
.section-lede{color:var(--muted);max-width:42rem;margin:0}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin:2.5rem 0 0;border-top:1px solid var(--rule)}
.stat{padding:1.6rem 1.25rem 1.6rem 0;border-bottom:1px solid var(--rule)}
.stat+.stat{padding-left:1.25rem;border-left:1px solid var(--rule)}
.stat dt{font-size:.8125rem;color:var(--muted);font-weight:500}
.stat dd{margin:.35rem 0 0;font:600 clamp(1.4rem,2.6vw,2.25rem)/1.1 var(--mono);letter-spacing:-.03em}
.stat:first-child dd{color:var(--gold)}
.series{margin-top:3rem;border-top:1px solid var(--rule)}
.series-head{display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:clamp(1.25rem,3.5vw,3rem);
align-items:start;padding:2.25rem 0 1.75rem}
.series-no{font:800 clamp(3.5rem,7vw,6rem)/.8 var(--sans);letter-spacing:-.06em;color:transparent;
-webkit-text-stroke:1.5px var(--c);transition:color .3s}
.series:hover .series-no{color:color-mix(in srgb,var(--c) 14%,transparent)}
.series h3{font-size:clamp(1.6rem,3vw,2.25rem);letter-spacing:-.035em;margin:0;line-height:1.05}
.series h3 a{text-decoration:none}
.series h3 a:hover{text-decoration:underline;text-decoration-color:var(--c);text-underline-offset:6px}
.series-head p{color:#cfcfcf;margin:.8rem 0 0;max-width:40rem}
.tags{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:1.1rem!important}
.tag{font:500 .75rem/1 var(--mono);padding:.45rem .65rem;border:1px solid var(--rule);border-radius:999px;color:var(--muted)}
.tag.live{color:var(--c);border-color:color-mix(in srgb,var(--c) 45%,transparent)}
.tag.live::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--c);
margin-right:.45rem;vertical-align:1px}
.editions{list-style:none;margin:0;padding:0;position:relative}
.edition{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;border-top:1px solid var(--rule);
position:relative}
.edition::before{content:"";position:absolute;left:clamp(1.6rem,3.2vw,2.75rem);top:50%;width:11px;height:11px;margin:-5.5px;
border-radius:50%;background:var(--ink);border:3px solid var(--c);z-index:1}
.editions::before{content:"";position:absolute;left:clamp(1.6rem,3.2vw,2.75rem);top:0;bottom:0;width:4px;margin-left:-2px;
background:color-mix(in srgb,var(--c) 55%,transparent)}
.edition-link{display:grid;grid-template-columns:clamp(3.5rem,6.5vw,5.75rem) 9.5rem minmax(0,1fr) minmax(0,1.6fr) auto;
gap:1rem;align-items:center;padding:1rem .75rem 1rem 0;text-decoration:none;transition:background .2s}
.edition-link::before{content:""}
.edition-link:hover{background:linear-gradient(90deg,transparent,#151515 30%)}
.edition-link:hover .arrow{transform:translateX(4px);color:var(--c)}
.ed-date{font:500 .875rem var(--mono);color:var(--text)}
.ed-main{display:flex;flex-direction:column;min-width:0}
.ed-title{font-weight:650}
.ed-period{font-size:.8125rem;color:var(--muted)}
.ed-hl{display:flex;flex-wrap:wrap;gap:.35rem 1.1rem;font:500 .8125rem var(--mono);color:var(--text)}
.hl span{color:var(--muted);font-family:var(--sans)}
.edition .arrow{transition:transform .2s,color .2s;color:var(--muted)}
.ed-json{font:500 .75rem var(--mono);color:var(--muted);text-decoration:none;padding:.35rem .55rem;border:1px solid var(--rule);
border-radius:6px;margin-right:.25rem}
.ed-json:hover{color:var(--gold);border-color:rgba(212,175,55,.5)}
.edition:first-child::before{background:var(--c)}
.more summary{cursor:pointer;font-weight:600;color:var(--muted);padding:1rem 0 1rem clamp(3.5rem,6.5vw,5.75rem);
border-top:1px solid var(--rule)}
.more summary:hover{color:var(--text)}
.route{list-style:none;padding:0;margin:3rem 0 0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));
gap:2rem;position:relative}
.route::before{content:"";position:absolute;left:0;right:12%;top:7px;height:7px;border-radius:4px;
background:linear-gradient(90deg,var(--gold-deep),var(--gold),var(--gold-pale));transform-origin:left;
transform:scaleX(var(--progress,1));transition:transform 1.4s cubic-bezier(.6,.05,.25,1)}
.stop{position:relative;display:block;width:21px;height:21px;border-radius:50%;background:var(--ink);border:4px solid var(--text)}
.step h3{font-size:1.25rem;margin:1.25rem 0 .5rem;letter-spacing:-.02em}
.step p{margin:0;color:#cfcfcf;font-size:.9688rem}
.split{display:grid;grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr);gap:clamp(2rem,6vw,5rem);align-items:start}
.split p{color:#cfcfcf;margin:0 0 1rem}
pre{margin:0;background:#0f0f0f;border:1px solid var(--rule);border-left:4px solid var(--gold);border-radius:8px;
padding:1.25rem 1.4rem;overflow-x:auto;font:400 .8125rem/1.7 var(--mono);color:#d4d4d4}
pre .k{color:var(--gold)}
pre .s{color:#f2efe6}
.cta-row{display:flex;flex-wrap:wrap;align-items:center;gap:1.25rem;margin-top:2rem}
.link{color:var(--gold);text-underline-offset:4px}
footer{background:var(--gold);color:var(--ink);padding:2.25rem 0}
footer .wrap{display:flex;flex-wrap:wrap;gap:1.5rem;align-items:center;justify-content:space-between;font-weight:600}
footer .brand small{color:var(--ink);opacity:.7}
footer nav{display:flex;gap:1.5rem;font-size:.9375rem}
footer nav a{text-decoration:underline;text-underline-offset:3px}
.reveal{opacity:0;transform:translateY(24px);transition:opacity .8s ease,transform .8s cubic-bezier(.2,.7,.2,1)}
.reveal.in{opacity:1;transform:none}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
@media (max-width:1100px){.edition-link{grid-template-columns:clamp(3.5rem,6.5vw,5.75rem) 8.5rem minmax(0,1fr) auto}
.ed-hl{grid-column:3/4;grid-row:2}}
@media (max-width:820px){.atlas{grid-template-columns:minmax(0,1fr)}.atlas>div:first-child{order:2}
.nav{display:none}.topbar .pill{margin-left:auto}.stats{grid-template-columns:1fr 1fr}
.stat:nth-child(3){padding-left:0;border-left:0}
.series-head{grid-template-columns:auto minmax(0,1fr)}.series-head .pill{grid-column:2;justify-self:start}
.route{grid-template-columns:1fr 1fr}.route::before{display:none}.split{grid-template-columns:1fr}}
@media (max-width:560px){.stat,.stat+.stat{padding-left:0;border-left:0}
.stat:nth-child(even){padding-left:1rem;border-left:1px solid var(--rule)}
.edition-link{grid-template-columns:2.75rem minmax(0,1fr) auto;row-gap:.35rem}
.ed-date{grid-column:2}.ed-main,.ed-hl{grid-column:2;grid-row:auto}.edition .arrow{grid-column:3;grid-row:1}
.editions::before,.edition::before{left:1.4rem}.more summary{padding-left:2.75rem}
.route{grid-template-columns:1fr}.topbar .pill .long{display:none}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:0s!important;animation-delay:0s!important;
transition-duration:0s!important}html{scroll-behavior:auto}.reveal{opacity:1;transform:none}}
@media print{.topbar,.map-card,footer{display:none}body{background:#fff;color:#000}}
"""

SCRIPT = """
(function () {
  var map = document.querySelector('.map');
  var card = document.getElementById('map-card');
  function field(name) { return card && card.querySelector('[data-field="' + name + '"]'); }
  function show(station) {
    if (!card) return;
    document.querySelectorAll('.station.is-active').forEach(function (s) { s.classList.remove('is-active'); });
    station.classList.add('is-active');
    var d = station.dataset;
    field('date').textContent = 'Published \\u00b7 ' + d.date;
    field('title').textContent = d.edition;
    field('body').textContent = d.highlights || 'Published edition.';
    field('report').textContent = d.report;
    field('chip').style.setProperty('--c', d.color);
  }
  if (map) {
    map.querySelectorAll('.station').forEach(function (s) {
      s.addEventListener('mouseenter', function () { show(s); });
    });
  }
  var buttons = document.querySelectorAll('.legend-item');
  buttons.forEach(function (b) {
    b.addEventListener('click', function () {
      var on = b.getAttribute('aria-pressed') !== 'true';
      buttons.forEach(function (o) { o.setAttribute('aria-pressed', 'false'); });
      if (!map) return;
      map.querySelectorAll('.line').forEach(function (l) {
        l.classList.toggle('is-focus', on && l.dataset.line === b.dataset.line);
      });
      if (on) { b.setAttribute('aria-pressed', 'true'); map.setAttribute('data-focus', ''); }
      else { map.removeAttribute('data-focus'); }
    });
  });
  var route = document.querySelector('.route');
  if (route) route.style.setProperty('--progress', '0');
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        e.target.classList.add('in');
        if (e.target === route) route.style.setProperty('--progress', '1');
        io.unobserve(e.target);
      });
    }, { threshold: 0.15 });
    document.querySelectorAll('.reveal').forEach(function (el) { io.observe(el); });
  } else {
    document.querySelectorAll('.reveal').forEach(function (el) { el.classList.add('in'); });
    if (route) route.style.setProperty('--progress', '1');
  }
})();
"""

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HemSoft Reports</title>
<meta name="description" content="Every report published by HemSoft Developments, with each edition kept on file.">
<meta name="theme-color" content="#0a0a0a">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 40'%3E%3Cg fill='%23d4af37'%3E%3Cpolygon points='63,1 3,25 15,25'/%3E%3Cpolygon points='63,1 17,32 28,32'/%3E%3Cpolygon points='63,1 31,39 41,39'/%3E%3C/g%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700;800&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="alternate" type="application/json" href="catalog.json" title="Report catalog">
<style>{style}</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="topbar">
  <div class="wrap">
    <a class="brand" href="#top" aria-label="HemSoft Reports, home">{mark}<span>HemSoft<small>Reports</small></span></a>
    <nav class="nav" aria-label="Sections">
      <a href="#map">The map</a><a href="#reports">Reports</a><a href="#publishing">Publishing</a>
    </nav>
    <a class="pill" href="{latest}"><span class="long">Latest edition</span><span class="sr-only"> (open the newest report)</span><span class="arrow" aria-hidden="true">→</span></a>
  </div>
</header>
<main id="main">
  <section class="hero" id="top">
    <div class="wrap">
      <p class="eyebrow">HemSoft Developments · Report index</p>
      <h1>Every report,<br><em>on one map.</em></h1>
      <p class="lede">Each line is a report series, and each stop is an edition, placed on the day it was published.
      Every edition stays on file with the data behind it. <strong>{reports} {reports_word}, {editions} {editions_word} so far.</strong></p>
      <div class="atlas" id="map">
        <div>
          <p class="legend-title">Lines</p>
          {legend}
          {card}
        </div>
        <div class="map-frame">{map}</div>
      </div>
    </div>
  </section>

  <section class="band" aria-labelledby="archive-title">
    <div class="wrap reveal">
      <h2 id="archive-title">The archive</h2>
      <p class="section-lede">Counted from <a class="link" href="catalog.json">catalog.json</a>, the index every page on this site is built from.</p>
      {stats}
    </div>
  </section>

  <section class="band" id="reports" aria-labelledby="reports-title">
    <div class="wrap">
      <h2 id="reports-title">Reports</h2>
      <p class="section-lede">Newest first. Each edition is a standalone page with its data saved next to it as JSON.</p>
      {directory}
    </div>
  </section>

  <section class="band" id="publishing" aria-labelledby="how-title">
    <div class="wrap reveal">
      <h2 id="how-title">How a report gets on the map</h2>
      <ol class="route">{steps}</ol>
    </div>
  </section>

  <section class="band" aria-labelledby="manifest-title">
    <div class="wrap split reveal">
      <div>
        <h2 id="manifest-title">One manifest, any report</h2>
        <p>Reports don't need to share anything but this file. A new kind of report becomes a new line the first time it is published.</p>
        <div class="cta-row"><a class="pill" href="catalog.json">Read the catalog <span class="arrow" aria-hidden="true">→</span></a></div>
      </div>
      <pre aria-label="Example edition manifest"><code>{manifest}</code></pre>
    </div>
  </section>
</main>
<footer>
  <div class="wrap">
    <span class="brand">{footer_mark}<span>HemSoft Developments<small>Reports, drawn as a map</small></span></span>
    <nav aria-label="Footer">
      <a href="catalog.json">catalog.json</a>
      <a href="https://github.com/HemSoft/reports">Source on GitHub</a>
    </nav>
  </div>
</footer>
<script>{script}</script>
</body>
</html>
"""
