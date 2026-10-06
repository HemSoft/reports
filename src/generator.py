import os
import json
from datetime import date
from zoneinfo import ZoneInfo
from .collector import cache_source_key, collect_all
from .analyzer import analyze_data
from .template import build_html_report
from .catalog import EDITION_HOME

EDT = ZoneInfo("America/New_York")


def generate_report(
    base_dir=r"D:\github\HemSoft",
    weeks=12,
    start_str=None,
    end_str=None,
    output_html=r"D:\hemsoft-productivity.html",
    refresh=False,
    json_out=None,
    edition_dir=None,
):
    print("=== HEMSOFT PRODUCTIVITY AUDIT GENERATOR ===")
    print(f"Target directory: {base_dir}")
    print(
        f"Report timeframe: {weeks} weeks"
        if not (start_str and end_str)
        else f"Timeframe: {start_str} to {end_str}"
    )

    cache_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(cache_dir, exist_ok=True)
    period = f"{weeks}w" if not (start_str and end_str) else f"{start_str}_{end_str}_{weeks}w"
    cache_file = os.path.join(cache_dir, f"cache_{cache_source_key(base_dir)}_{period}.json")

    # 1. Collect Data
    raw_data = collect_all(
        base_dir,
        weeks=weeks,
        start_str=start_str,
        end_str=end_str,
        cache_file=cache_file,
        refresh=refresh,
    )

    # 2. Analyze Data
    print("Computing metrics, time distributions, 3D matrices, and repository profiles...")
    analysis = analyze_data(raw_data)

    # Optional JSON export
    if json_out:
        os.makedirs(os.path.dirname(os.path.abspath(json_out)), exist_ok=True)
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2)
        print(f"Exported metrics JSON to {json_out}")

    # 3. Build HTML Dashboard
    print("Rendering interactive HTML dashboard with 3D bars and analytics...")
    html_report = build_html_report(analysis)

    out_dir = os.path.dirname(os.path.abspath(output_html))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_report)

    print(f"Successfully generated HTML report at: {output_html}")
    print(f"Report file size: {len(html_report):,} bytes")

    if edition_dir:
        manifest = write_edition(analysis, edition_dir)
        print(f"Wrote publishable edition manifest to {manifest}")

    return output_html, analysis


REPORT = {
    "id": "productivity",
    "title": "Engineering Productivity Audit",
    "summary": (
        "Throughput, pull request velocity, code churn and coding cadence across HemSoft "
        "repositories, with WebGL views of weekly velocity and the 168 hours of the week."
    ),
    "category": "Engineering",
    "cadence": "Weekly · Mondays 12:00 UTC",
}


def _signed(value):
    """Signed figure short enough for a highlight: +12,345, −2.50M."""
    sign = "−" if value < 0 else "+"
    size = abs(value)
    return f"{sign}{size / 1_000_000:.2f}M" if size >= 1_000_000 else f"{sign}{size:,}"


def _hours(value):
    return f"{value * 60:.0f} min" if value < 1 else f"{value:.1f} h"


def _edition_identity(period):
    """Relative windows are named by their end date; custom ranges by both dates."""
    days = (date.fromisoformat(period["end_date"]) - date.fromisoformat(period["start_date"])).days
    if days == period["weeks"] * 7:
        return period["end_date"], f"{period['weeks']} weeks to {period['end_formatted']}"
    return (
        f"{period['start_date']}-to-{period['end_date']}",
        f"{period['start_formatted']} – {period['end_formatted']}",
    )


def edition_manifest(analysis):
    kpis, period = analysis["kpis"], analysis["range"]
    edition_id, title = _edition_identity(period)
    return {
        "report": REPORT,
        "edition": {
            "id": edition_id,
            "title": title,
            "period": {"start": period["start_formatted"], "end": period["end_formatted"]},
            "highlights": [
                {"label": "Commits", "value": f"{kpis['total_commits']:,}"},
                {"label": "PRs merged", "value": f"{kpis['merged_prs']:,}"},
                {"label": "Net lines", "value": _signed(kpis["net_lines"])},
                {"label": "Median PR cycle", "value": _hours(kpis["median_pr_cycle_hours"])},
                {"label": "Active repos", "value": f"{kpis['active_repos_count']:,}"},
                {"label": "Longest streak", "value": f"{kpis['longest_streak']} days"},
            ],
        },
        "files": {"html": "report.html", "payload": "payload.json"},
    }


def write_edition(analysis, edition_dir):
    """Write report.html, payload.json and manifest.json for `publish.py add`."""
    os.makedirs(edition_dir, exist_ok=True)
    with open(os.path.join(edition_dir, "report.html"), "w", encoding="utf-8") as f:
        f.write(build_html_report(analysis, home_href=EDITION_HOME))
    with open(os.path.join(edition_dir, "payload.json"), "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2)
    manifest = os.path.join(edition_dir, "manifest.json")
    with open(manifest, "w", encoding="utf-8") as f:
        json.dump(edition_manifest(analysis), f, indent=2, ensure_ascii=False)
    return manifest
