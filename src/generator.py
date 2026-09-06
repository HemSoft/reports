import os
import json
from zoneinfo import ZoneInfo
from .collector import cache_source_key, collect_all
from .analyzer import analyze_data
from .template import build_html_report

EDT = ZoneInfo("America/New_York")


def generate_report(
    base_dir=r"D:\github\HemSoft",
    weeks=12,
    start_str=None,
    end_str=None,
    output_html=r"D:\hemsoft-productivity.html",
    refresh=False,
    json_out=None,
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

    return output_html, analysis
