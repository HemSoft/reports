import json
import html
from datetime import datetime
from zoneinfo import ZoneInfo

from src.branding import BRAND_MARK
from src.browser_assets import graphics_script
from src.github_identity import repository_identity

VISUALIZATIONS = {
    "velocity": "Weekly velocity in three dimensions",
    "cadence": "Day and hour cadence in three dimensions",
    "weekly-combo": "Weekly cadence and cumulative lines added",
    "day-distribution": "Commits by day of week",
    "hour-distribution": "Commits by hour of day",
    "repo-share": "Repository commit share",
    "pr-cycle": "Pull request cycle duration",
    "commit-categories": "Commit categories",
    "languages": "Language additions and deletions",
}


def _data_table(key, columns, rows):
    name = html.escape(VISUALIZATIONS[key])
    headings = "".join(f'<th scope="col">{html.escape(str(column))}</th>' for column in columns)
    body = ""
    for row in rows:
        cells = f'<th scope="row">{html.escape(str(row[0]))}</th>'
        cells += "".join(f"<td>{html.escape(str(value))}</td>" for value in row[1:])
        body += f"<tr>{cells}</tr>"
    return (
        f'<details class="chart-data" id="data-{key}">'
        f'<summary id="data-summary-{key}">View {name} data</summary>'
        f'<div class="table-wrap" tabindex="0" role="region" aria-label="{name} data table">'
        f"<table><caption>{name} data</caption><thead><tr>{headings}</tr></thead>"
        f"<tbody>{body}</tbody></table></div></details>"
    )


def _weekly_table_rows(weekly):
    rows = []
    cumulative = 0
    for week in weekly:
        cumulative += week["additions"]
        rows.append(
            [
                week["label"],
                week["start_date"],
                week["end_date"],
                week["commits"],
                week["prs_opened"],
                week["prs_merged"],
                week["issues_closed"],
                week["additions"],
                week["deletions"],
                week["net_lines"],
                week["human_commits"],
                week["ai_commits"],
                week["active_days"],
                week["top_repo"],
                cumulative,
            ]
        )
    return rows


def _visualization_tables(data):
    temporal = data["temporal"]
    weekly_columns = [
        "Week",
        "Start",
        "End",
        "Commits",
        "PRs opened",
        "PRs merged",
        "Issues closed",
        "Lines added",
        "Lines deleted",
        "Net lines",
        "Human commits",
        "AI commits",
        "Active days",
        "Top repository",
        "Cumulative lines added",
    ]
    weekly_rows = _weekly_table_rows(data["weekly_data"])
    cycle_labels = [
        "Less than 1 hour",
        "1 to less than 4 hours",
        "4 to less than 24 hours",
        "24 to less than 72 hours",
        "72 hours or more",
    ]
    cycle_keys = ["under_1h", "1h_to_4h", "4h_to_24h", "1d_to_3d", "over_3d"]
    return {
        "velocity": _data_table("velocity", weekly_columns, weekly_rows),
        "weekly-combo": _data_table("weekly-combo", weekly_columns, weekly_rows),
        "cadence": _data_table(
            "cadence",
            ["Day (America/New_York)"] + [f"{h:02d}:00" for h in range(24)],
            [[day, *values] for day, values in zip(temporal["day_names"], temporal["matrix_7x24"])],
        ),
        "day-distribution": _data_table(
            "day-distribution", ["Day", "Commits"], temporal["day_counts"].items()
        ),
        "hour-distribution": _data_table(
            "hour-distribution",
            ["Hour (America/New_York)", "Commits"],
            [[f"{int(hour):02d}:00", count] for hour, count in temporal["hour_counts"].items()],
        ),
        "repo-share": _data_table(
            "repo-share",
            ["Repository", "Commits"],
            [[repo["name"], repo["commits"]] for repo in data["repo_profiles"][:8]],
        ),
        "pr-cycle": _data_table(
            "pr-cycle",
            ["Duration", "Merged PRs"],
            [
                [label, data["kpis"]["pr_cycle_distribution"][key]]
                for label, key in zip(cycle_labels, cycle_keys)
            ],
        ),
        "commit-categories": _data_table(
            "commit-categories", ["Category", "Commits"], data["category_distribution"].items()
        ),
        "languages": _data_table(
            "languages",
            ["Language", "Lines added", "Lines deleted"],
            [
                [language["language"], language["additions"], language["deletions"]]
                for language in data["language_breakdown"][:7]
            ],
        ),
    }


def _script_json(value):
    """Serialize data without exposing HTML parser delimiters inside a script."""
    return json.dumps(value).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _generated_label(timestamp):
    """Keep collection freshness, including cached data, in Eastern Time."""
    if not timestamp:
        return "Unknown"
    generated = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if generated.utcoffset() is None:
        raise ValueError("generated_at must include a timezone")
    eastern = generated.astimezone(ZoneInfo("America/New_York"))
    return eastern.strftime("%b %d, %Y %H:%M:%S %Z (UTC%z)")


def build_html_report(analytics_data, home_href=None):
    kpis = analytics_data["kpis"]
    range_info = analytics_data["range"]
    weekly = analytics_data["weekly_data"]
    repos = analytics_data["repo_profiles"]
    languages = analytics_data["language_breakdown"]
    temporal = analytics_data["temporal"]
    authors = analytics_data["author_distribution"]
    categories = analytics_data["category_distribution"]
    recent_prs = analytics_data.get("recent_prs", [])
    recent_commits = analytics_data.get("recent_commits", [])
    chart_tables = _visualization_tables(analytics_data)
    generated_label = _generated_label(analytics_data.get("generated_at"))
    home_link = (
        f'<a class="btn" href="{html.escape(home_href, quote=True)}">All reports</a>'
        if home_href
        else ""
    )
    cycle_distribution = kpis["pr_cycle_distribution"]
    measured_prs = sum(cycle_distribution.values())
    under_hour_pct = 100 * cycle_distribution["under_1h"] / measured_prs if measured_prs else 0

    # JSON payloads for charts
    json_weekly = _script_json(weekly)
    json_repos = _script_json(repos)
    json_languages = _script_json(languages)
    json_temporal = _script_json(temporal)
    json_matrix = _script_json(temporal["matrix_7x24"])
    json_categories = _script_json(categories)
    json_authors = _script_json(authors)
    json_kpis = _script_json(kpis)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Engineering productivity audit | HemSoft Reports</title>
  
  <!-- Chart.js and Three.js CDNs -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.js" integrity="sha384-hfkuqrKeWFmnTMWN31VWyoe8xgdTADD11kgxmdpx2uyE6j5Az5uZq6u6AKYYmAOw" crossorigin="anonymous"></script>
  {graphics_script()}

  <style>
    :root {{
      color-scheme: dark;
      --bg-primary: #0a0a0a;
      --bg-secondary: #141414;
      --bg-tertiary: #242424;
      --bg-card: #141414;
      --border-color: rgba(255, 255, 255, 0.08);
      --border-accent: rgba(212, 175, 55, 0.3);
      --text-primary: #f5f5f5;
      --text-secondary: #ababab;
      --text-muted: #ababab;
      --accent-gold: #d4af37;
      --accent-steel: #7ca7be;
      --accent-ochre: #b8a074;
      --accent-slate: #abb7c4;
      --accent-emerald: #68b894;
      --accent-amber: #e0bd58;
      --accent-rose: #e7898a;
      --font-sans: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif;
      --font-mono: ui-monospace, 'SFMono-Regular', Consolas, monospace;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      background-color: var(--bg-primary);
      color: var(--text-primary);
      font-family: var(--font-sans);
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
    }}

    ::selection {{ background: var(--accent-gold); color: var(--bg-primary); }}
    a {{ text-underline-offset: .2em; }}
    input {{ caret-color: var(--accent-gold); }}
    input::placeholder {{ color: var(--text-secondary); opacity: 1; }}
    * {{ scrollbar-width: thin; scrollbar-color: #565656 var(--bg-secondary); }}
    table, .kpi-value, .time-badge {{ font-variant-numeric: tabular-nums; }}
    .report-bar {{ padding-bottom: 1.5rem; margin-bottom: 2rem; border-bottom: 1px solid var(--border-color); }}
    .report-brand {{ display: inline-flex; align-items: center; gap: .65rem; color: var(--text-primary); font-weight: 650; text-decoration: none; }}
    .report-brand .mark {{ width: 32px; height: 20px; color: var(--accent-gold); flex-shrink: 0; }}

    /* Container */
    .dashboard-container {{
      max-width: 1600px;
      margin: 0 auto;
      padding: 2rem 2.5rem 4rem 2.5rem;
    }}

    /* Header & Hero */
    header {{
      display: flex;
      flex-wrap: wrap;
      gap: 1.5rem;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 2.5rem;
      padding-bottom: 2rem;
      border-bottom: 1px solid var(--border-color);
      position: relative;
    }}

    .header-brand {{
      display: flex;
      flex: 1 1 34rem;
      min-width: 0;
      align-items: center;
      gap: 1.25rem;
    }}

    .title-group {{ min-width: 0; }}

    .title-group h1 {{
      font-size: 2.2rem;
      font-weight: 650;
      letter-spacing: -0.03em;
      margin-bottom: 0.25rem;
    }}

    .title-group .meta-bar {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 1rem;
      font-size: 0.9rem;
      color: var(--text-secondary);
    }}

    .meta-bar > span:last-child {{ flex-basis: 100%; }}

    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.25rem 0.65rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}

    .badge-gold {{
      background: rgba(212, 175, 55, 0.15);
      color: var(--accent-gold);
      border: 1px solid rgba(212, 175, 55, 0.3);
    }}

    .badge-slate {{
      background: rgba(171, 183, 196, 0.15);
      color: var(--accent-slate);
      border: 1px solid rgba(171, 183, 196, 0.3);
    }}

    .badge-emerald {{
      background: rgba(104, 184, 148, 0.15);
      color: var(--accent-emerald);
      border: 1px solid rgba(104, 184, 148, 0.3);
    }}

    .header-actions {{
      display: flex;
      flex: 1 1 22rem;
      max-width: 100%;
      flex-direction: column;
      align-items: flex-end;
      gap: 0.75rem;
    }}

    .time-badge {{
      max-width: 100%;
      overflow-wrap: anywhere;
      font-family: var(--font-mono);
      font-size: 0.85rem;
      padding: 0.5rem 1rem;
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 10px;
      color: var(--text-secondary);
    }}

    .time-badge strong {{
      color: var(--accent-gold);
    }}

    .btn-group {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }}

    .btn {{
      padding: 0.5rem 1rem;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
      border: 1px solid var(--border-color);
      background: var(--bg-secondary);
      color: var(--text-primary);
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
    }}

    .btn:hover {{
      background: var(--bg-tertiary);
      border-color: var(--accent-gold);
    }}

    /* Executive Persona Badges */
    .persona-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      margin-bottom: 2.5rem;
    }}

    .persona-pill {{
      display: flex;
      align-items: center;
      gap: 0.6rem;
      padding: 0.6rem 1rem;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      font-size: 0.85rem;
      color: var(--text-secondary);
      transition: all 0.2s;
    }}

    .persona-pill:hover {{
      border-color: var(--border-accent);
      transform: translateY(-2px);
    }}

    .persona-pill .icon {{
      font-size: 1.1rem;
    }}

    .persona-pill strong {{
      color: var(--text-primary);
      font-weight: 600;
    }}

    /* KPI Grid */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1.25rem;
      margin-bottom: 3rem;
    }}

    .kpi-card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      padding: 1.5rem;
      position: relative;
      overflow: hidden;
      transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }}

    .kpi-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.75rem;
    }}

    .kpi-label {{
      font-size: 0.8rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
    }}

    .kpi-icon {{
      font-size: 1.2rem;
      opacity: 0.8;
    }}

    .kpi-value {{
      font-size: 2.2rem;
      font-weight: 650;
      letter-spacing: -0.03em;
      color: var(--text-primary);
      font-family: var(--font-sans);
      margin-bottom: 0.25rem;
    }}

    .kpi-subtext {{
      font-size: 0.8rem;
      color: var(--text-secondary);
      display: flex;
      align-items: center;
      gap: 0.35rem;
    }}

    .text-emerald {{ color: var(--accent-emerald) !important; }}
    .text-gold {{ color: var(--accent-gold) !important; }}
    .text-slate {{ color: var(--accent-slate) !important; }}
    .text-amber {{ color: var(--accent-amber) !important; }}
    .text-rose {{ color: var(--accent-rose) !important; }}

    /* Section Headings */
    .section-title-wrap {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      margin-bottom: 1.5rem;
      margin-top: 3.5rem;
    }}

    .section-title {{
      font-size: 1.5rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }}

    .section-desc {{
      font-size: 0.9rem;
      color: var(--text-muted);
    }}

    /* 3D Visualizer Containers */
    .three-row {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 1.5rem;
      margin-bottom: 3rem;
    }}

    @media (max-width: 1200px) {{
      .three-row {{
        grid-template-columns: minmax(0, 1fr);
      }}
    }}

    .three-card {{
      min-width: 0;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 20px;
      padding: 1.5rem;
      position: relative;
      overflow: hidden;
    }}

    .three-header {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
      z-index: 10;
      position: relative;
    }}

    .three-title {{
      flex: 1 1 20rem;
      min-width: 0;
      font-size: 1.1rem;
      font-weight: 600;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}

    .three-controls {{
      display: flex;
      flex-wrap: wrap;
      flex-shrink: 0;
      gap: 0.5rem;
    }}

    .three-btn {{
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(255, 255, 255, 0.1);
      color: var(--text-secondary);
      border-radius: 6px;
      padding: 0.25rem 0.6rem;
      font-size: 0.75rem;
      cursor: pointer;
      transition: all 0.2s;
    }}

    .three-btn:hover, .three-btn.active {{
      background: var(--accent-gold);
      color: var(--bg-primary);
      border-color: var(--accent-gold);
    }}

    .three-viewport {{
      width: 100%;
      height: 480px;
      border-radius: 12px;
      background: #0a0a0a;
      position: relative;
      cursor: grab;
      overflow: hidden;
    }}

    .three-viewport:active {{
      cursor: grabbing;
    }}

    .visualization-unavailable {{
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: default;
    }}

    .visualization-fallback {{
      max-width: 34rem;
      padding: 1.5rem;
      color: var(--text-secondary);
      line-height: 1.6;
      text-align: center;
    }}

    .three-btn:disabled {{
      opacity: 0.45;
      cursor: not-allowed;
    }}

    .chart-data {{
      margin-top: 1rem;
      color: var(--text-secondary);
      min-width: 0;
    }}

    .chart-data summary {{
      cursor: pointer;
      padding: 0.5rem 0;
    }}

    .chart-data table {{ font-size: 0.85rem; }}
    .chart-data th {{ color: var(--text-secondary); font-size: 0.8rem; }}
    .chart-data th[scope="row"], .chart-data thead th:first-child {{
      position: sticky;
      left: 0;
      z-index: 1;
      background: var(--bg-secondary);
      border-right: 1px solid rgba(255, 255, 255, 0.08);
    }}
    .chart-data caption {{ text-align: left; padding: 0.5rem; }}
    :focus-visible {{ outline: 2px solid var(--accent-gold); outline-offset: 3px; }}

    .three-hint {{
      position: absolute;
      bottom: 12px;
      left: 14px;
      font-size: 0.75rem;
      color: var(--text-muted);
      background: rgba(0, 0, 0, 0.65);
      padding: 0.2rem 0.6rem;
      border-radius: 6px;
      pointer-events: none;
    }}

    .three-tooltip {{
      position: absolute;
      background: #141414;
      border: 1px solid var(--accent-gold);
      border-radius: 8px;
      padding: 0.5rem 0.75rem;
      font-size: 0.8rem;
      color: #fff;
      pointer-events: none;
      opacity: 0;
      transition: opacity 0.15s;
      z-index: 50;
      box-shadow: 0 4px 20px rgba(0,0,0,0.6);
      font-family: var(--font-mono);
    }}

    /* 2D Chart Cards Grid */
    .chart-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 1.5rem;
      margin-bottom: 3rem;
    }}

    @media (max-width: 1024px) {{
      .chart-grid {{
        grid-template-columns: minmax(0, 1fr);
      }}
    }}

    .chart-card {{
      min-width: 0;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 18px;
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
    }}

    .chart-card.full-width {{
      grid-column: 1 / -1;
    }}

    .chart-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.25rem;
    }}

    .chart-title {{
      font-size: 1.05rem;
      font-weight: 600;
      color: var(--text-primary);
    }}

    .chart-subtitle {{
      font-size: 0.8rem;
      color: var(--text-muted);
    }}

    .chart-canvas-wrap {{
      position: relative;
      flex: 1;
      min-height: 280px;
    }}

    /* Table Styles */
    .table-card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 18px;
      padding: 1.5rem;
      margin-bottom: 3rem;
    }}

    .table-toolbar {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.25rem;
      gap: 1rem;
    }}

    .search-input {{
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 0.5rem 1rem;
      color: var(--text-primary);
      font-size: 0.85rem;
      width: 320px;
      max-width: 100%;
      font-family: var(--font-sans);
    }}

    .search-input:focus {{
      outline: none;
      border-color: var(--accent-gold);
      outline: 2px solid var(--accent-gold);
      outline-offset: 3px;
    }}

    .table-wrap {{
      overflow-x: auto;
      min-width: 0;
      max-width: 100%;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 0.875rem;
    }}

    th {{
      padding: 0.75rem 1rem;
      color: var(--text-muted);
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      border-bottom: 1px solid var(--border-color);
      background: rgba(255, 255, 255, 0.02);
    }}

    td {{
      padding: 0.9rem 1rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      color: var(--text-secondary);
    }}

    tr:hover td {{
      background: rgba(255, 255, 255, 0.02);
      color: var(--text-primary);
    }}

    .repo-name {{
      font-family: var(--font-mono);
      font-weight: 600;
      color: var(--accent-gold);
      text-decoration: none;
    }}

    .repo-name:hover {{
      text-decoration: underline;
    }}

    .commit-hash {{
      font-family: var(--font-mono);
      color: var(--accent-gold);
      background: rgba(212, 175, 55, 0.1);
      padding: 0.2rem 0.4rem;
      border-radius: 4px;
      font-size: 0.75rem;
      text-decoration: none;
    }}

    .progress-bar-bg {{
      width: 100%;
      height: 6px;
      background: rgba(255, 255, 255, 0.08);
      border-radius: 3px;
      overflow: hidden;
      margin-top: 4px;
    }}

    .progress-bar-fill {{
      height: 100%;
      border-radius: 3px;
      background: var(--accent-gold);
    }}

    /* Tabs */
    .tabs-nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-bottom: 1.5rem;
      border-bottom: 1px solid var(--border-color);
      padding-bottom: 0.75rem;
    }}

    .tab-btn {{
      padding: 0.5rem 1.25rem;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 600;
      background: transparent;
      border: 1px solid transparent;
      color: var(--text-secondary);
      cursor: pointer;
      transition: all 0.2s;
    }}

    .tab-btn:hover {{
      color: var(--text-primary);
      background: var(--bg-secondary);
    }}

    .tab-btn.active {{
      color: var(--accent-gold);
      background: rgba(212, 175, 55, 0.1);
      border-color: rgba(212, 175, 55, 0.3);
    }}

    .tab-pane {{
      display: none;
    }}

    .tab-pane.active {{
      display: block;
    }}

    /* Footer */
    footer {{
      margin-top: 5rem;
      padding-top: 2rem;
      border-top: 1px solid var(--border-color);
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      overflow-wrap: anywhere;
      justify-content: space-between;
      align-items: center;
      color: var(--text-muted);
      font-size: 0.85rem;
    }}

    footer a {{
      color: var(--accent-gold);
      text-decoration: underline;
    }}

    @media (max-width: 600px) {{
      .dashboard-container {{ padding: 1.25rem 1rem 2rem; }}
      .header-brand {{ flex-direction: column; align-items: flex-start; gap: 1rem; }}
      .header-brand, .header-actions {{ flex-basis: 100%; }}
      .header-actions {{ align-items: stretch; }}
      .title-group .meta-bar {{ gap: 0.5rem; }}
      .btn-group .btn {{ flex: 1 1 10rem; justify-content: center; }}
      .btn, .three-btn, .tab-btn {{ min-height: 44px; }}
      .three-card, .chart-card, .table-card {{ padding: 1rem; }}
      .three-title {{ flex-basis: 100%; }}
      .three-viewport {{ height: 360px; }}
      .three-hint {{ left: 0.5rem; right: 0.5rem; bottom: 0.5rem; }}
      .table-toolbar {{ align-items: stretch; }}
      .tabs-nav, .search-input {{ width: 100%; }}
      .tabs-nav {{ gap: 0.25rem; }}
      .tab-btn {{ flex: 1 1 100%; text-align: left; }}
    }}

    @media print {{
      :root {{
        color-scheme: light;
        --bg-primary: #fff; --bg-secondary: #fff; --bg-card: #fff;
        --border-color: #ccc; --text-primary: #111;
        --text-secondary: #444; --text-muted: #444;
        --accent-gold: #755b00; --accent-slate: #444;
        --accent-emerald: #30513a; --accent-amber: #755b00; --accent-rose: #803b3b;
      }}
      .three-card, .btn-group, .search-input, .tabs-nav {{ display: none !important; }}
      .tab-pane, .tab-pane[hidden] {{ display: block !important; }}
      .table-wrap {{ overflow: visible; }}
      .table-card, .kpi-card, .chart-card {{ break-inside: avoid; }}
      .table-card {{ break-inside: auto; }}
    }}
  </style>
</head>
<body>

<main class="dashboard-container">
  <div class="report-bar">
    <a class="report-brand" href="{
        html.escape(home_href or "https://hemsoft.github.io/reports/", quote=True)
    }" aria-label="HemSoft Reports, home">
      {BRAND_MARK}<span>HemSoft Reports</span>
    </a>
  </div>
  
  <!-- Header -->
  <header>
    <div class="header-brand">
      <div class="title-group">
        <h1>Engineering productivity audit</h1>
        <div class="meta-bar">
          <span>Franz Hemmer</span>
          <span>Period: <strong>{range_info["start_formatted"]} – {
        range_info["end_formatted"]
    }</strong></span>
        </div>
      </div>
    </div>
    
    <div class="header-actions">
      <div class="time-badge">
        Data generated: <strong>{
        generated_label
    }</strong> | Timezone: <strong>America/New_York (ET)</strong>
      </div>
      <div class="btn-group">
        {home_link}
        <button class="btn" onclick="window.print()">Print / Export PDF</button>
        <a class="btn" href="https://github.com/HemSoft" target="_blank" rel="noopener">GitHub Profile</a>
      </div>
    </div>
  </header>

  <!-- Engineering Persona Highlights -->
  <div class="persona-bar">
    <div class="persona-pill">
      <span class="icon">⚡</span>
      <div><strong>Ultra-Rapid PR Delivery:</strong> {
        kpis["pr_cycle_distribution"]["under_1h"]
    } PRs merged under 1 hour (Median: {kpis["median_pr_cycle_hours"]}h)</div>
    </div>
    <div class="persona-pill">
      <span class="icon">🤖</span>
      <div><strong>Agentic Pipeline:</strong> {kpis["merged_prs"]:,} merged PRs across {
        kpis["active_repos_count"]
    } repositories</div>
    </div>
    <div class="persona-pill">
      <span class="icon">🧹</span>
      <div><strong>Radical Pruning:</strong> {
        kpis["total_deletions"]:,} lines deleted (codebase lean & fast)</div>
    </div>
    <div class="persona-pill">
      <span class="icon">🦉</span>
      <div><strong>Night Owl Rhythm:</strong> {
        kpis["night_owl_ratio"]
    }% of commits during late night/early morning ET</div>
    </div>
    <div class="persona-pill">
      <span class="icon">🔥</span>
      <div><strong>Consistency:</strong> {kpis["active_days_count"]} active days ({
        kpis["active_days_pct"]
    }%) with {kpis["longest_streak"]}-day streak</div>
    </div>
  </div>

  <!-- Hero KPI Grid -->
  <div class="kpi-grid">
    <div class="kpi-card" style="--card-accent: var(--accent-gold);">
      <div class="kpi-header">
        <span class="kpi-label">Total Commits</span>
        <span class="kpi-icon">📦</span>
      </div>
      <div class="kpi-value text-gold">{kpis["total_commits"]:,}</div>
      <div class="kpi-subtext">Across {kpis["active_repos_count"]} active repositories</div>
    </div>

    <div class="kpi-card" style="--card-accent: var(--accent-slate);">
      <div class="kpi-header">
        <span class="kpi-label">Pull Requests Merged</span>
        <span class="kpi-icon">🔀</span>
      </div>
      <div class="kpi-value text-slate">{kpis["merged_prs"]:,}</div>
      <div class="kpi-subtext"><span class="text-emerald"><strong>{
        kpis["pr_merge_rate"]
    }%</strong></span> merge rate ({kpis["total_prs"]:,} total)</div>
    </div>

    <div class="kpi-card" style="--card-accent: var(--accent-emerald);">
      <div class="kpi-header">
        <span class="kpi-label">Issues Resolved</span>
        <span class="kpi-icon">🎯</span>
      </div>
      <div class="kpi-value text-emerald">{kpis["closed_issues"]:,}</div>
      <div class="kpi-subtext"><span class="text-emerald"><strong>{
        kpis["issue_close_rate"]
    }%</strong></span> close rate ({kpis["total_issues"]:,} total)</div>
    </div>

    <div class="kpi-card" style="--card-accent: var(--accent-amber);">
      <div class="kpi-header">
        <span class="kpi-label">Median Turnaround</span>
        <span class="kpi-icon">⏱️</span>
      </div>
      <div class="kpi-value text-amber">{kpis["median_pr_cycle_hours"]}h</div>
      <div class="kpi-subtext">Average: {kpis["avg_pr_cycle_hours"]}h to merge</div>
    </div>

    <div class="kpi-card" style="--card-accent: var(--accent-gold);">
      <div class="kpi-header">
        <span class="kpi-label">Lines Shipped (+)</span>
        <span class="kpi-icon">📈</span>
      </div>
      <div class="kpi-value text-emerald">+{kpis["total_additions"]:,}</div>
      <div class="kpi-subtext">Across {kpis["total_unique_files"]:,} unique files</div>
    </div>

    <div class="kpi-card" style="--card-accent: var(--accent-rose);">
      <div class="kpi-header">
        <span class="kpi-label">Lines Pruned (-)</span>
        <span class="kpi-icon">✂️</span>
      </div>
      <div class="kpi-value text-rose">-{kpis["total_deletions"]:,}</div>
      <div class="kpi-subtext">Net delta: {kpis["net_lines"]:,} lines</div>
    </div>

    <div class="kpi-card" style="--card-accent: var(--accent-steel);">
      <div class="kpi-header">
        <span class="kpi-label">Active Coding Cadence</span>
        <span class="kpi-icon">📅</span>
      </div>
      <div class="kpi-value">{
        kpis["active_days_count"]
    } <span style="font-size: 1.1rem; color: var(--text-muted);">/ {
        kpis["total_calendar_days"]
    }d</span></div>
      <div class="kpi-subtext">{kpis["active_days_pct"]}% active | {
        kpis["avg_commits_per_active_day"]
    } commits/active day</div>
    </div>

    <div class="kpi-card" style="--card-accent: var(--accent-slate);">
      <div class="kpi-header">
        <span class="kpi-label">Peak Productivity Day</span>
        <span class="kpi-icon">🚀</span>
      </div>
      <div class="kpi-value text-gold" style="font-size: 1.7rem; padding-top: 0.3rem;">{
        kpis["peak_day"]["date"]
    }</div>
      <div class="kpi-subtext"><strong>{kpis["peak_day"]["commits"]} commits</strong> (+{
        kpis["peak_day"]["additions"]:,} lines)</div>
    </div>
  </div>

  <!-- SECTION: 3D INTERACTIVE VISUALIZATIONS -->
  <div class="section-title-wrap">
    <div>
      <h2 class="section-title">3D Productivity Engine Visualizations</h2>
      <p class="section-desc">Interactive WebGL 3D volumetric models of velocity, temporal cadence, and repository throughput. Click and drag to orbit, scroll to zoom.</p>
    </div>
  </div>

  <div class="three-row">
    <!-- 3D Weekly Velocity Multi-Bar Chart -->
    <div class="three-card" data-visualization="velocity" role="region" aria-label="Weekly velocity in three dimensions">
      <div class="three-header">
        <div class="three-title">
          <span>📊</span> 3D Weekly Velocity & Throughput
        </div>
        <div class="three-controls">
          <button class="three-btn active" id="btn-3d-vel-autorotate" aria-label="Auto-rotate weekly velocity" aria-pressed="true" onclick="toggleAutoRotate('vel')">Auto-Rotate</button>
          <button class="three-btn" aria-label="Reset weekly velocity camera" onclick="resetCamera('vel')">Reset View</button>
        </div>
      </div>
      <div class="three-viewport" id="viewport-velocity">
        <div class="three-hint">Left Drag: Orbit | Right Drag: Pan | Scroll: Zoom | Hover: Inspect Bar</div>
        <div class="three-tooltip" id="tooltip-velocity"></div>
      </div>
      {chart_tables["velocity"]}
    </div>

    <!-- 3D Day x Hour Productivity Landscape -->
    <div class="three-card" data-visualization="cadence" role="region" aria-label="Day and hour cadence in three dimensions">
      <div class="three-header">
        <div class="three-title">
          <span>🏙️</span> 3D Cadence Landscape (Day × Hour Matrix ET)
        </div>
        <div class="three-controls">
          <button class="three-btn active" id="btn-3d-cad-autorotate" aria-label="Auto-rotate day and hour cadence" aria-pressed="true" onclick="toggleAutoRotate('cad')">Auto-Rotate</button>
          <button class="three-btn" aria-label="Reset day and hour cadence camera" onclick="resetCamera('cad')">Reset View</button>
        </div>
      </div>
      <div class="three-viewport" id="viewport-cadence">
        <div class="three-hint">Left Drag: Orbit | Right Drag: Pan | Scroll: Zoom | Hover: Inspect Hour</div>
        <div class="three-tooltip" id="tooltip-cadence"></div>
      </div>
      {chart_tables["cadence"]}
    </div>
  </div>

  <!-- SECTION: 2D CHARTS & METRICS BREAKDOWN -->
  <div class="section-title-wrap">
    <div>
      <h2 class="section-title">Velocity & Delivery Analytics</h2>
      <p class="section-desc">Comprehensive trend analysis of commit velocity, PR cycle times, language distribution, and temporal rhythms.</p>
    </div>
  </div>

  <div class="chart-grid">
    <!-- Weekly Velocity Combo Chart -->
    <div class="chart-card full-width" data-visualization="weekly-combo" role="region" aria-label="Weekly cadence and cumulative lines added">
      <div class="chart-header">
        <div>
          <div class="chart-title">Weekly Cadence & Cumulative Lines Shipped</div>
          <div class="chart-subtitle">Commits and merged PRs with cumulative lines added from {
        range_info["start_formatted"]
    } through {range_info["end_formatted"]}</div>
        </div>
      </div>
      <div class="chart-canvas-wrap" style="height: 340px;">
        <canvas id="chart-weekly-combo" role="img" aria-label="Weekly cadence and cumulative lines added" aria-describedby="data-summary-weekly-combo">Equivalent values are available in the data table below.</canvas>
      </div>
      {chart_tables["weekly-combo"]}
    </div>

    <!-- 2D Heatmap: Day of Week & Hour Distribution -->
    <div class="chart-card" data-visualization="day-distribution" role="region" aria-label="Commits by day of week">
      <div class="chart-header">
        <div>
          <div class="chart-title">Day of Week Activity Matrix</div>
          <div class="chart-subtitle">Commit distribution across days (ET)</div>
        </div>
      </div>
      <div class="chart-canvas-wrap">
        <canvas id="chart-day-distribution" role="img" aria-label="Commits by day of week" aria-describedby="data-summary-day-distribution">Equivalent values are available in the data table below.</canvas>
      </div>
      {chart_tables["day-distribution"]}
    </div>

    <!-- Hour of Day Distribution -->
    <div class="chart-card" data-visualization="hour-distribution" role="region" aria-label="Commits by hour of day">
      <div class="chart-header">
        <div>
          <div class="chart-title">24-Hour Diurnal Rhythm (America/New_York)</div>
          <div class="chart-subtitle">Hourly distribution highlighting Night Owl vs Daytime coding</div>
        </div>
      </div>
      <div class="chart-canvas-wrap">
        <canvas id="chart-hour-distribution" role="img" aria-label="Commits by hour of day" aria-describedby="data-summary-hour-distribution">Equivalent values are available in the data table below.</canvas>
      </div>
      {chart_tables["hour-distribution"]}
    </div>

    <!-- Repository Effort Share -->
    <div class="chart-card" data-visualization="repo-share" role="region" aria-label="Repository commit share">
      <div class="chart-header">
        <div>
          <div class="chart-title">Repository Contribution Share</div>
          <div class="chart-subtitle">Relative commit volume across top active repositories</div>
        </div>
      </div>
      <div class="chart-canvas-wrap">
        <canvas id="chart-repo-share" role="img" aria-label="Repository commit share" aria-describedby="data-summary-repo-share">Equivalent values are available in the data table below.</canvas>
      </div>
      {chart_tables["repo-share"]}
    </div>

    <!-- PR Cycle Time & Resolution Speed -->
    <div class="chart-card" data-visualization="pr-cycle" role="region" aria-label="Pull request cycle duration">
      <div class="chart-header">
        <div>
          <div class="chart-title">PR Turnaround Velocity Distribution</div>
          <div class="chart-subtitle">Time from PR opening to merge ({
        under_hour_pct:.1f}% under 1 hour; measured merged PRs)</div>
        </div>
      </div>
      <div class="chart-canvas-wrap">
        <canvas id="chart-pr-cycle" role="img" aria-label="Pull request cycle duration" aria-describedby="data-summary-pr-cycle">Equivalent values are available in the data table below.</canvas>
      </div>
      {chart_tables["pr-cycle"]}
    </div>

    <!-- Commit Discipline / Categories -->
    <div class="chart-card" data-visualization="commit-categories" role="region" aria-label="Commit categories">
      <div class="chart-header">
        <div>
          <div class="chart-title">Engineering Discipline Breakdown</div>
          <div class="chart-subtitle">Conventional commit categorization (Features, Fixes, Refactoring, CI/DevOps)</div>
        </div>
      </div>
      <div class="chart-canvas-wrap">
        <canvas id="chart-commit-categories" role="img" aria-label="Commit categories" aria-describedby="data-summary-commit-categories">Equivalent values are available in the data table below.</canvas>
      </div>
      {chart_tables["commit-categories"]}
    </div>

    <!-- Language & Stack Churn -->
    <div class="chart-card" data-visualization="languages" role="region" aria-label="Language additions and deletions">
      <div class="chart-header">
        <div>
          <div class="chart-title">Language & Technology Churn</div>
          <div class="chart-subtitle">Lines added vs deleted across primary languages</div>
        </div>
      </div>
      <div class="chart-canvas-wrap">
        <canvas id="chart-languages" role="img" aria-label="Language additions and deletions" aria-describedby="data-summary-languages">Equivalent values are available in the data table below.</canvas>
      </div>
      {chart_tables["languages"]}
    </div>
  </div>

  <!-- SECTION: REPOSITORY DEEP DIVE & EXPLORER -->
  <div class="section-title-wrap">
    <div>
      <h2 class="section-title">Repository Matrix & Audit Log</h2>
      <p class="section-desc">Granular statistics for every repository touched during the selected audit interval.</p>
    </div>
  </div>

  <div class="table-card">
    <div class="table-toolbar">
      <div class="tabs-nav" role="tablist" aria-label="Report tables" style="margin-bottom: 0; border-bottom: none;">
        <button class="tab-btn active" id="tab-repos" role="tab" aria-controls="pane-repos" aria-selected="true" tabindex="0" onclick="switchTab('repos')">Repositories ({
        len(repos)
    })</button>
        <button class="tab-btn" id="tab-prs" role="tab" aria-controls="pane-prs" aria-selected="false" tabindex="-1" onclick="switchTab('prs')">Recent Pull Requests ({
        len(recent_prs)
    })</button>
        <button class="tab-btn" id="tab-commits" role="tab" aria-controls="pane-commits" aria-selected="false" tabindex="-1" onclick="switchTab('commits')">Recent Commits ({
        len(recent_commits)
    })</button>
      </div>
      <input type="search" class="search-input" id="table-search" aria-label="Filter the selected report table" placeholder="Filter repositories, PRs, or commits..." oninput="filterCurrentTable()">
    </div>

    <!-- TAB 1: REPOSITORIES -->
    <div class="tab-pane active" id="pane-repos" role="tabpanel" aria-labelledby="tab-repos" tabindex="0">
      <div class="table-wrap">
        <table id="table-repos">
          <thead>
            <tr>
              <th>Repository</th>
              <th>Visibility</th>
              <th>Language</th>
              <th>Commits</th>
              <th>Share</th>
              <th>Lines Added</th>
              <th>Lines Deleted</th>
              <th>Net Delta</th>
              <th>PRs (Merged / Total)</th>
              <th>Issues Closed</th>
              <th>Active Days</th>
            </tr>
          </thead>
          <tbody>
            {
        "".join(
            f'''<tr>
              <td><a class="repo-name" href="https://github.com/{repository_identity(r['name'], r.get('github_repository'))}" target="_blank">{html.escape(r['name'])}</a><br><small style="color: var(--text-muted);">{html.escape(r['description'][:60])}</small></td>
              <td><span class="badge {'badge-slate' if r['is_private'] else 'badge-gold'}">{'Private' if r['is_private'] else 'Public'}</span></td>
              <td><strong>{r['primary_language']}</strong></td>
              <td><strong>{r['commits']:,}</strong></td>
              <td>
                <span style="font-size: 0.8rem;">{r['commits_share']}%</span>
                <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: {min(100, r['commits_share'] * 3)}%;"></div></div>
              </td>
              <td class="text-emerald">+{r['additions']:,}</td>
              <td class="text-rose">-{r['deletions']:,}</td>
              <td><strong class="{'text-emerald' if r['net_lines'] >= 0 else 'text-amber'}">{r['net_lines']:,}</strong></td>
              <td><strong>{r['prs_merged']}</strong> / {r['prs_total']}</td>
              <td><strong>{r['issues_closed']}</strong></td>
              <td>{r['active_days']}d</td>
            </tr>'''
            for r in repos
        )
    }
          </tbody>
        </table>
      </div>
    </div>

    <!-- TAB 2: PULL REQUESTS -->
    <div class="tab-pane" id="pane-prs" role="tabpanel" aria-labelledby="tab-prs" tabindex="0" hidden>
      <div class="table-wrap">
        <table id="table-prs">
          <thead>
            <tr>
              <th>PR #</th>
              <th>Repository</th>
              <th>Title</th>
              <th>Status</th>
              <th>Cycle Time</th>
              <th>Created</th>
              <th>Link</th>
            </tr>
          </thead>
          <tbody>
            {
        "".join(
            f'''<tr>
              <td><span class="commit-hash">#{p.get('number')}</span></td>
              <td><span class="repo-name">{p.get('repo')}</span></td>
              <td>{html.escape(p.get('title', ''))}</td>
              <td><span class="badge {'badge-emerald' if p.get('state') == 'MERGED' else 'badge-gold' if p.get('state') == 'OPEN' else 'badge-slate'}">{p.get('state')}</span></td>
              <td><strong>{str(p.get('cycle_hours')) + 'h' if p.get('cycle_hours') is not None else '–'}</strong></td>
              <td style="font-family: var(--font-mono); font-size: 0.75rem;">{p.get('createdAt', '')[:10]}</td>
              <td><a href="{p.get('url')}" target="_blank" class="commit-hash">View PR ↗</a></td>
            </tr>'''
            for p in recent_prs
        )
    }
          </tbody>
        </table>
      </div>
    </div>

    <!-- TAB 3: COMMITS -->
    <div class="tab-pane" id="pane-commits" role="tabpanel" aria-labelledby="tab-commits" tabindex="0" hidden>
      <div class="table-wrap">
        <table id="table-commits">
          <thead>
            <tr>
              <th>Hash</th>
              <th>Repo</th>
              <th>Date (ET)</th>
              <th>Subject</th>
              <th>Category</th>
              <th>Author</th>
              <th>Diff</th>
            </tr>
          </thead>
          <tbody>
            {
        "".join(
            f'''<tr>
              <td><a href="https://github.com/{repository_identity(c['repo'], c.get('github_repository'))}/commit/{html.escape(c['hash'], quote=True)}" target="_blank" class="commit-hash">{html.escape(c['hash'][:8])}</a></td>
              <td><span class="repo-name">{c['repo']}</span></td>
              <td style="font-family: var(--font-mono); font-size: 0.75rem;">{c['author_date'][:16].replace('T', ' ')}</td>
              <td>{html.escape(c['subject'])}</td>
              <td><span class="badge badge-gold">{c['category']}</span></td>
              <td><small>{html.escape(c['author_name'])}</small></td>
              <td><span class="text-emerald">+{c['additions']}</span> / <span class="text-rose">-{c['deletions']}</span></td>
            </tr>'''
            for c in recent_commits
        )
    }
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- FOOTER -->
  <footer>
    <div>
      <strong>HemSoft Developments</strong> · <a href="https://github.com/HemSoft/reports">Report source</a>
    </div>
    <div>
      Audited Period: {range_info["start_formatted"]} – {range_info["end_formatted"]}
    </div>
  </footer>

</main>

<!-- DATA & INTERACTIVE SCRIPTS -->
<script>
  const weeklyData = {json_weekly};
  const repoData = {json_repos};
  const langData = {json_languages};
  const temporalData = {json_temporal};
  const matrix7x24 = {json_matrix};
  const catData = {json_categories};
  const authorData = {json_authors};
  const kpiData = {json_kpis};

  // ==========================================
  // THREE.JS SCENE 1: 3D WEEKLY VELOCITY BARS
  // ==========================================
  let velScene, velCamera, velRenderer, velControls, velFrame, velBars = [];
  let velAutoRotate = true;

  function initVelocity3D() {{
    const container = document.getElementById('viewport-velocity');
    const width = container.clientWidth;
    const height = container.clientHeight;

    velScene = new THREE.Scene();
    velScene.background = new THREE.Color(0x0a0a0a);
    velScene.fog = new THREE.FogExp2(0x0a0a0a, 0.015);

    velCamera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    velCamera.position.set(28, 26, 36);

    velRenderer = new THREE.WebGLRenderer({{ antialias: true }});
    velRenderer.setSize(width, height);
    velRenderer.setPixelRatio(window.devicePixelRatio);
    velRenderer.shadowMap.enabled = true;
    nameCanvas(velRenderer.domElement, 'velocity');
    container.appendChild(velRenderer.domElement);

    velControls = new THREE.OrbitControls(velCamera, velRenderer.domElement);
    velControls.enableDamping = true;
    velControls.dampingFactor = 0.05;
    velControls.target.set(0, 4, 0);

    // Grid floor
    const grid = new THREE.GridHelper(50, 25, 0xd4af37, 0x303030);
    grid.position.y = 0;
    velScene.add(grid);

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    velScene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(20, 40, 20);
    dirLight.castShadow = true;
    velScene.add(dirLight);

    const pointLight = new THREE.PointLight(0xd4af37, 1.2, 50);
    pointLight.position.set(0, 15, 0);
    velScene.add(pointLight);

    // Create 3D Bars for each week
    const numWeeks = weeklyData.length;
    const spacingX = 3.2;
    const startX = -((numWeeks - 1) * spacingX) / 2;

    const commitMaterial = new THREE.MeshStandardMaterial({{
      color: 0xd4af37,
      metalness: 0.3,
      roughness: 0.2,
      emissive: 0x4b3d13,
      emissiveIntensity: 0.2
    }});

    const prMaterial = new THREE.MeshStandardMaterial({{
      color: 0xabb7c4,
      metalness: 0.3,
      roughness: 0.2,
      emissive: 0x30343a,
      emissiveIntensity: 0.2
    }});

    const linesMaterial = new THREE.MeshStandardMaterial({{
      color: 0x68b894,
      metalness: 0.3,
      roughness: 0.2,
      emissive: 0x203c30,
      emissiveIntensity: 0.2
    }});

    weeklyData.forEach((w, idx) => {{
      const x = startX + idx * spacingX;

      // 1. Commits Bar
      const cHeight = Math.max(0.4, (w.commits / 180) * 16);
      const cGeo = new THREE.BoxGeometry(0.8, cHeight, 0.8);
      const cMesh = new THREE.Mesh(cGeo, commitMaterial.clone());
      cMesh.position.set(x, cHeight / 2, -2.5);
      cMesh.castShadow = true;
      cMesh.userData = {{ week: w.label, range: w.range_str, metric: 'Commits', value: w.commits, details: `${{w.human_commits}} Human / ${{w.ai_commits}} AI` }};
      velScene.add(cMesh);
      velBars.push(cMesh);

      // 2. PRs Merged Bar
      const prHeight = Math.max(0.4, (w.prs_merged / 100) * 16);
      const prGeo = new THREE.BoxGeometry(0.8, prHeight, 0.8);
      const prMesh = new THREE.Mesh(prGeo, prMaterial.clone());
      prMesh.position.set(x, prHeight / 2, 0);
      prMesh.castShadow = true;
      prMesh.userData = {{ week: w.label, range: w.range_str, metric: 'Merged PRs', value: w.prs_merged, details: `Opened: ${{w.prs_opened}}` }};
      velScene.add(prMesh);
      velBars.push(prMesh);

      // 3. Additions / 10k Bar
      const lHeight = Math.max(0.4, (w.additions / 120000) * 16);
      const lGeo = new THREE.BoxGeometry(0.8, lHeight, 0.8);
      const lMesh = new THREE.Mesh(lGeo, linesMaterial.clone());
      lMesh.position.set(x, lHeight / 2, 2.5);
      lMesh.castShadow = true;
      lMesh.userData = {{ week: w.label, range: w.range_str, metric: 'Lines Added', value: '+' + w.additions.toLocaleString(), details: `Pruned: -${{w.deletions.toLocaleString()}}` }};
      velScene.add(lMesh);
      velBars.push(lMesh);
    }});

    // Raycaster for hover
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    const tooltip = document.getElementById('tooltip-velocity');

    container.addEventListener('mousemove', (e) => {{
      const rect = container.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / container.clientWidth) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / container.clientHeight) * 2 + 1;

      raycaster.setFromCamera(mouse, velCamera);
      const intersects = raycaster.intersectObjects(velBars);

      if (intersects.length > 0) {{
        const hit = intersects[0].object;
        const d = hit.userData;
        tooltip.innerHTML = `<strong>${{d.week}} (${{d.range}})</strong><br><span style="color:var(--accent-gold);">${{d.metric}}: <strong>${{d.value}}</strong></span><br><small style="color:var(--text-muted);">${{d.details}}</small>`;
        tooltip.style.left = (e.clientX - rect.left + 15) + 'px';
        tooltip.style.top = (e.clientY - rect.top - 20) + 'px';
        tooltip.style.opacity = 1;
        hit.material.emissiveIntensity = 0.6;
      }} else {{
        tooltip.style.opacity = 0;
        velBars.forEach(b => b.material.emissiveIntensity = 0.2);
      }}
    }});

    container.addEventListener('mouseleave', () => {{
      tooltip.style.opacity = 0;
      velBars.forEach(b => b.material.emissiveIntensity = 0.2);
    }});

    function animate() {{
      velFrame = requestAnimationFrame(animate);
      if (velAutoRotate) {{
        velScene.rotation.y += 0.003;
      }}
      velControls.update();
      velRenderer.render(velScene, velCamera);
    }}
    animate();

    window.addEventListener('resize', () => {{
      const w = container.clientWidth;
      const h = container.clientHeight;
      velCamera.aspect = w / h;
      velCamera.updateProjectionMatrix();
      velRenderer.setSize(w, h);
    }});
  }}

  // ========================================================
  // THREE.JS SCENE 2: 3D CADENCE LANDSCAPE (7 DAYS x 24 HOURS)
  // ========================================================
  let cadScene, cadCamera, cadRenderer, cadControls, cadFrame, cadBars = [];
  let cadAutoRotate = true;

  function initCadence3D() {{
    const container = document.getElementById('viewport-cadence');
    const width = container.clientWidth;
    const height = container.clientHeight;

    cadScene = new THREE.Scene();
    cadScene.background = new THREE.Color(0x0a0a0a);
    cadScene.fog = new THREE.FogExp2(0x0a0a0a, 0.015);

    cadCamera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    cadCamera.position.set(32, 28, 32);

    cadRenderer = new THREE.WebGLRenderer({{ antialias: true }});
    cadRenderer.setSize(width, height);
    cadRenderer.setPixelRatio(window.devicePixelRatio);
    cadRenderer.shadowMap.enabled = true;
    nameCanvas(cadRenderer.domElement, 'cadence');
    container.appendChild(cadRenderer.domElement);

    cadControls = new THREE.OrbitControls(cadCamera, cadRenderer.domElement);
    cadControls.enableDamping = true;
    cadControls.dampingFactor = 0.05;
    cadControls.target.set(0, 2, 0);

    const grid = new THREE.GridHelper(40, 24, 0x8c784c, 0x303030);
    cadScene.add(grid);

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    cadScene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(20, 30, 10);
    cadScene.add(dirLight);

    const dayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    const maxVal = Math.max(...matrix7x24.flat(), 1);

    // Cadence intensity: dark ochre through pale gold
    function getBarColor(val) {{
      const ratio = val / maxVal;
      if (ratio < 0.25) return new THREE.Color(0x514326); // low activity
      if (ratio < 0.55) return new THREE.Color(0x8c784c); // moderate activity
      if (ratio < 0.8)  return new THREE.Color(0xd4af37); // high activity
      return new THREE.Color(0xf1d78a); // peak activity
    }}

    const spacingX = 2.4;
    const spacingZ = 1.1;
    const startX = - (6 * spacingX) / 2;
    const startZ = - (23 * spacingZ) / 2;

    for (let d = 0; d < 7; d++) {{
      for (let h = 0; h < 24; h++) {{
        const count = matrix7x24[d][h];
        const barH = Math.max(0.15, (count / maxVal) * 12);
        const geo = new THREE.BoxGeometry(1.6, barH, 0.8);
        const color = getBarColor(count);
        
        const mat = new THREE.MeshStandardMaterial({{
          color: color,
          metalness: 0.4,
          roughness: 0.3,
          emissive: color,
          emissiveIntensity: count > 0 ? 0.3 : 0.05
        }});

        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.set(startX + d * spacingX, barH / 2, startZ + h * spacingZ);
        mesh.userData = {{ day: dayLabels[d], hour: `${{h}}:00 ET`, count: count }};
        cadScene.add(mesh);
        cadBars.push(mesh);
      }}
    }}

    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    const tooltip = document.getElementById('tooltip-cadence');

    container.addEventListener('mousemove', (e) => {{
      const rect = container.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / container.clientWidth) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / container.clientHeight) * 2 + 1;

      raycaster.setFromCamera(mouse, cadCamera);
      const intersects = raycaster.intersectObjects(cadBars);

      if (intersects.length > 0) {{
        const hit = intersects[0].object;
        const d = hit.userData;
        tooltip.innerHTML = `<strong>${{d.day}} @ ${{d.hour}}</strong><br><span style="color:var(--accent-amber); font-size:1.1rem; font-weight:700;">${{d.count}} Commits</span>`;
        tooltip.style.left = (e.clientX - rect.left + 15) + 'px';
        tooltip.style.top = (e.clientY - rect.top - 20) + 'px';
        tooltip.style.opacity = 1;
        hit.material.emissiveIntensity = 0.8;
      }} else {{
        tooltip.style.opacity = 0;
        cadBars.forEach(b => b.material.emissiveIntensity = b.userData.count > 0 ? 0.3 : 0.05);
      }}
    }});

    container.addEventListener('mouseleave', () => {{
      tooltip.style.opacity = 0;
      cadBars.forEach(b => b.material.emissiveIntensity = b.userData.count > 0 ? 0.3 : 0.05);
    }});

    function animate() {{
      cadFrame = requestAnimationFrame(animate);
      if (cadAutoRotate) {{
        cadScene.rotation.y += 0.003;
      }}
      cadControls.update();
      cadRenderer.render(cadScene, cadCamera);
    }}
    animate();

    window.addEventListener('resize', () => {{
      const w = container.clientWidth;
      const h = container.clientHeight;
      cadCamera.aspect = w / h;
      cadCamera.updateProjectionMatrix();
      cadRenderer.setSize(w, h);
    }});
  }}

  function toggleAutoRotate(scene) {{
    if (scene === 'vel') {{
      velAutoRotate = !velAutoRotate;
      document.getElementById('btn-3d-vel-autorotate').classList.toggle('active', velAutoRotate);
      document.getElementById('btn-3d-vel-autorotate').setAttribute('aria-pressed', String(velAutoRotate));
    }} else {{
      cadAutoRotate = !cadAutoRotate;
      document.getElementById('btn-3d-cad-autorotate').classList.toggle('active', cadAutoRotate);
      document.getElementById('btn-3d-cad-autorotate').setAttribute('aria-pressed', String(cadAutoRotate));
    }}
  }}

  // Damping decays per frame, so on slow devices a drag keeps drifting for seconds.
  // Applying the leftover motion with damping off clears it before the reset.
  function stopMomentum(controls) {{
    controls.enableDamping = false;
    controls.update();
    controls.enableDamping = true;
  }}

  function resetCamera(scene) {{
    if (scene === 'vel') {{
      stopMomentum(velControls);
      velCamera.position.set(28, 26, 36);
      velControls.target.set(0, 4, 0);
      velScene.rotation.set(0, 0, 0);
      velControls.update();
    }} else {{
      stopMomentum(cadControls);
      cadCamera.position.set(32, 28, 32);
      cadControls.target.set(0, 2, 0);
      cadScene.rotation.set(0, 0, 0);
      cadControls.update();
    }}
  }}

  // ==========================================
  // CHART.JS INITIALIZATION
  // ==========================================
  function nameCanvas(canvas, key) {{
    const region = document.querySelector(`[data-visualization="${{key}}"]`);
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', region.getAttribute('aria-label'));
    canvas.setAttribute('aria-describedby', `data-summary-${{key}}`);
    canvas.textContent = 'Equivalent values are available in the data table below.';
  }}

  function showVisualizationFallback(container, message) {{
    const notice = document.createElement('p');
    notice.className = 'visualization-fallback';
    notice.setAttribute('role', 'status');
    notice.textContent = message;
    container.replaceChildren(notice);
    container.classList.add('visualization-unavailable');
  }}

  function initializeScene(containerId, initialize, resources) {{
    try {{
      initialize();
    }} catch (error) {{
      const container = document.getElementById(containerId);
      const {{ renderer, controls, frame }} = resources();
      if (frame !== undefined) cancelAnimationFrame(frame);
      try {{
        controls?.dispose();
        renderer?.dispose();
        renderer?.forceContextLoss();
      }} catch (cleanupError) {{
        // A failed graphics context must not prevent the fallback.
      }}
      container.closest('.three-card').querySelectorAll('button').forEach(button => {{
        button.disabled = true;
        button.classList.remove('active');
        if (button.hasAttribute('aria-pressed')) button.setAttribute('aria-pressed', 'false');
      }});
      showVisualizationFallback(container,
        '3D view unavailable. Its graphics library could not load or WebGL could not start. Report metrics and tables remain available.');
    }}
  }}

  function createChart(canvas, config) {{
    try {{
      const chart = new Chart(canvas, config);
      if (!chart.ctx) throw new Error('Canvas context unavailable');
      return chart;
    }} catch (error) {{
      try {{ Chart.getChart(canvas)?.destroy(); }} catch (cleanupError) {{}}
      showVisualizationFallback(canvas.parentElement,
        'Chart unavailable. The chart could not initialize. Report metrics and tables remain available.');
      return null;
    }}
  }}

  function showChartLibraryFallbacks() {{
    document.querySelectorAll('.chart-canvas-wrap canvas').forEach(canvas => {{
      showVisualizationFallback(canvas.parentElement,
        'Chart unavailable. The chart library could not load. Report metrics and tables remain available.');
    }});
  }}

  function initCharts() {{
    if (typeof Chart === 'undefined') {{
      showChartLibraryFallbacks();
      return;
    }}
    Chart.defaults.color = '#ababab';
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;

    // 1. Weekly Combo Chart
    const weeklyLabels = weeklyData.map(w => w.label);
    const weeklyCommits = weeklyData.map(w => w.commits);
    const weeklyPrs = weeklyData.map(w => w.prs_merged);
    
    // Cumulative lines added
    let cum = 0;
    const cumLines = weeklyData.map(w => {{
      cum += w.additions;
      return cum;
    }});

    createChart(document.getElementById('chart-weekly-combo'), {{
      type: 'bar',
      data: {{
        labels: weeklyLabels,
        datasets: [
          {{
            label: 'Commits',
            data: weeklyCommits,
            backgroundColor: 'rgba(212, 175, 55, 0.75)',
            borderColor: '#d4af37',
            borderWidth: 1,
            borderRadius: 6,
            yAxisID: 'y'
          }},
          {{
            label: 'Merged PRs',
            data: weeklyPrs,
            backgroundColor: 'rgba(171, 183, 196, 0.75)',
            borderColor: '#abb7c4',
            borderWidth: 1,
            borderRadius: 6,
            yAxisID: 'y'
          }},
          {{
            label: 'Cumulative Lines Added',
            data: cumLines,
            type: 'line',
            borderColor: '#68b894',
            backgroundColor: 'rgba(104, 184, 148, 0.1)',
            borderWidth: 3,
            tension: 0.3,
            fill: true,
            yAxisID: 'y1'
          }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        scales: {{
          x: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
          y: {{
            type: 'linear',
            position: 'left',
            grid: {{ color: 'rgba(255,255,255,0.05)' }},
            title: {{ display: true, text: 'Commits / PRs' }}
          }},
          y1: {{
            type: 'linear',
            position: 'right',
            grid: {{ drawOnChartArea: false }},
            title: {{ display: true, text: 'Cumulative LoC' }}
          }}
        }}
      }}
    }});

    // 2. Day of Week Distribution
    createChart(document.getElementById('chart-day-distribution'), {{
      type: 'bar',
      data: {{
        labels: Object.keys(temporalData.day_counts),
        datasets: [{{
          label: 'Commits',
          data: Object.values(temporalData.day_counts),
          backgroundColor: [
            'rgba(212, 175, 55, 0.7)',
            'rgba(212, 175, 55, 0.7)',
            'rgba(212, 175, 55, 0.7)',
            'rgba(212, 175, 55, 0.7)',
            'rgba(212, 175, 55, 0.7)',
            'rgba(224, 189, 88, 0.8)',
            'rgba(224, 189, 88, 0.8)'
          ],
          borderRadius: 6
        }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{
          x: {{ grid: {{ display: false }} }},
          y: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }} }}
        }}
      }}
    }});

    // 3. Hour of Day Distribution
    const hourLabels = Array.from({{length: 24}}, (_, i) => `${{i}}:00`);
    const hourValues = Object.values(temporalData.hour_counts);
    createChart(document.getElementById('chart-hour-distribution'), {{
      type: 'line',
      data: {{
        labels: hourLabels,
        datasets: [{{
          label: 'Commits by Hour (ET)',
          data: hourValues,
          borderColor: '#abb7c4',
          backgroundColor: 'rgba(171, 183, 196, 0.15)',
          fill: true,
          tension: 0.35,
          borderWidth: 2.5,
          pointRadius: 4,
          pointHoverRadius: 6
        }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{ legend: {{ display: false }} }},
        scales: {{
          x: {{ grid: {{ display: false }} }},
          y: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }} }}
        }}
      }}
    }});

    // 4. Repo Contribution Share
    const topRepos = repoData.slice(0, 8);
    createChart(document.getElementById('chart-repo-share'), {{
      type: 'doughnut',
      data: {{
        labels: topRepos.map(r => r.name),
        datasets: [{{
          data: topRepos.map(r => r.commits),
          backgroundColor: [
            '#d4af37', '#abb7c4', '#68b894', '#7ca7be',
            '#e7898a', '#c99b76', '#b8a074', '#b09eaf'
          ],
          borderWidth: 2,
          borderColor: '#141414'
        }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          legend: {{ position: 'right', labels: {{ boxWidth: 12 }} }}
        }}
      }}
    }});

    // 5. PR Cycle Turnaround
    const cycleData = kpiData.pr_cycle_distribution;
    createChart(document.getElementById('chart-pr-cycle'), {{
      type: 'polarArea',
      data: {{
        labels: ['< 1 Hour', '1 - 4 Hours', '4 - 24 Hours', '1 - 3 Days', '> 3 Days'],
        datasets: [{{
          data: [cycleData.under_1h, cycleData['1h_to_4h'], cycleData['4h_to_24h'], cycleData['1d_to_3d'], cycleData.over_3d],
          backgroundColor: [
            'rgba(104, 184, 148, 0.8)',
            'rgba(212, 175, 55, 0.8)',
            'rgba(184, 160, 116, 0.8)',
            'rgba(224, 189, 88, 0.8)',
            'rgba(231, 137, 138, 0.8)'
          ]
        }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{ legend: {{ position: 'bottom' }} }}
      }}
    }});

    // 6. Commit Category Radar
    createChart(document.getElementById('chart-commit-categories'), {{
      type: 'radar',
      data: {{
        labels: Object.keys(catData),
        datasets: [{{
          label: 'Commits',
          data: Object.values(catData),
          backgroundColor: 'rgba(212, 175, 55, 0.25)',
          borderColor: '#d4af37',
          pointBackgroundColor: '#d4af37',
          borderWidth: 2
        }}]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        scales: {{
          r: {{
            grid: {{ color: 'rgba(255,255,255,0.08)' }},
            angleLines: {{ color: 'rgba(255,255,255,0.08)' }},
            pointLabels: {{ color: '#ababab', font: {{ size: 11 }} }}
          }}
        }}
      }}
    }});

    // 7. Languages Churn
    const topLangs = langData.slice(0, 7);
    createChart(document.getElementById('chart-languages'), {{
      type: 'bar',
      data: {{
        labels: topLangs.map(l => l.language),
        datasets: [
          {{
            label: 'Lines Added',
            data: topLangs.map(l => l.additions),
            backgroundColor: 'rgba(104, 184, 148, 0.75)',
            borderRadius: 4
          }},
          {{
            label: 'Lines Deleted',
            data: topLangs.map(l => l.deletions),
            backgroundColor: 'rgba(231, 137, 138, 0.75)',
            borderRadius: 4
          }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        scales: {{
          x: {{ grid: {{ display: false }} }},
          y: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }} }}
        }}
      }}
    }});
  }}

  function updateChartTheme() {{
    if (typeof Chart === 'undefined') return;
    const style = getComputedStyle(document.body);
    const text = style.getPropertyValue('--text-secondary').trim();
    const printing = window.matchMedia('print').matches;
    document.querySelectorAll('.chart-canvas-wrap canvas').forEach(canvas => {{
      const chart = Chart.getChart(canvas);
      if (!chart) return;
      chart.options.color = text;
      chart.options.plugins.legend.labels.color = text;
      Object.values(chart.options.scales || {{}}).forEach(scale => {{
        scale.ticks.color = text;
        scale.grid.color = printing ? 'rgba(0,0,0,0.12)' : 'rgba(255,255,255,0.05)';
        if (scale.type === 'radialLinear') {{
          scale.pointLabels.color = text;
          scale.angleLines.color = scale.grid.color;
        }}
      }});
      chart.update('none');
    }});
  }}

  window.matchMedia('print').addEventListener('change', updateChartTheme);

  // Table Tabs & Filtering
  function switchTab(tabId) {{
    ['repos', 'prs', 'commits'].forEach(id => {{
      const selected = id === tabId;
      const tab = document.getElementById(`tab-${{id}}`);
      const pane = document.getElementById(`pane-${{id}}`);
      tab.classList.toggle('active', selected);
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
      pane.classList.toggle('active', selected);
      pane.hidden = !selected;
    }});
    filterCurrentTable();
  }}

  document.querySelector('[role="tablist"]').addEventListener('keydown', event => {{
    const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
    const current = tabs.indexOf(event.target);
    if (current < 0 || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    let next = event.key === 'ArrowLeft' ? (current + tabs.length - 1) % tabs.length
      : (current + 1) % tabs.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = tabs.length - 1;
    tabs[next].focus();
    switchTab(tabs[next].id.replace('tab-', ''));
  }});

  function filterCurrentTable() {{
    const term = document.getElementById('table-search').value.toLowerCase();
    const activePane = document.querySelector('.tab-pane.active');
    const rows = activePane.querySelectorAll('tbody tr');
    
    rows.forEach(r => {{
      const text = r.innerText.toLowerCase();
      r.style.display = text.includes(term) ? '' : 'none';
    }});
  }}

  window.addEventListener('DOMContentLoaded', () => {{
    initializeScene('viewport-velocity', initVelocity3D,
      () => ({{ renderer: velRenderer, controls: velControls, frame: velFrame }}));
    initializeScene('viewport-cadence', initCadence3D,
      () => ({{ renderer: cadRenderer, controls: cadControls, frame: cadFrame }}));
    try {{ initCharts(); }} catch (error) {{ showChartLibraryFallbacks(); }}
  }});
</script>

</body>
</html>
"""
    return html_content
