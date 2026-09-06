"""Generate repeatable, synthetic small/large report inputs without collection."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def main():
    from report_fixture import load_report_fixture
    from src.analyzer import analyze_data
    from src.template import build_html_report

    output = ROOT / "test-results/performance"
    output.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for size, weeks, repositories, commits, prs in (
        ("small", 12, 20, 1200, 200),
        ("large", 52, 200, 20000, 2000),
    ):
        data = load_report_fixture()
        seed_commit = data["commits"][0]
        seed_pr = data["prs"]["hs-buddy"][0]
        start = datetime(2025, 9, 7, tzinfo=ZoneInfo("America/New_York"))
        end = start + timedelta(days=weeks * 7) - timedelta(seconds=1)
        data["range"] = {
            "weeks": weeks,
            "start_iso": start.isoformat(),
            "end_iso": end.isoformat(),
            "start_date": start.date().isoformat(),
            "end_date": end.date().isoformat(),
            "start_formatted": start.strftime("%b %d, %Y"),
            "end_formatted": end.strftime("%b %d, %Y"),
        }
        data["commits"], data["prs"], data["issues"], data["repo_meta"] = [], {}, {}, {}
        for index in range(repositories):
            repo = f"synthetic-repository-{index:03}"
            data["repo_meta"][repo] = {
                "description": "Synthetic benchmark activity",
                "isPrivate": False,
            }
            data["prs"][repo], data["issues"][repo] = [], []
        names = list(data["repo_meta"])
        for index in range(commits):
            date = start + timedelta(seconds=index * weeks * 7 * 86400 // commits)
            data["commits"].append(
                {
                    **seed_commit,
                    "hash": f"{index:040x}",
                    "repo": names[index % repositories],
                    "author_date": date.isoformat(),
                    "timestamp": int(date.timestamp()),
                    "day_of_week": date.strftime("%A"),
                    "day_index": date.weekday(),
                    "hour": date.hour,
                    "date_str": date.date().isoformat(),
                }
            )
        for index in range(prs):
            date = start + timedelta(hours=index * weeks * 7 * 24 // prs)
            repo = names[index % repositories]
            data["prs"][repo].append(
                {
                    **seed_pr,
                    "number": index + 1,
                    "repo": repo,
                    "createdAt": date.isoformat(),
                    "mergedAt": (date + timedelta(minutes=30)).isoformat(),
                }
            )
            if index % 2 == 0:
                data["issues"][repo].append(
                    {"state": "CLOSED", "createdAt": date.isoformat(), "closedAt": date.isoformat()}
                )
        analysis = analyze_data(data)
        html = build_html_report(analysis)
        (output / f"{size}.html").write_text(html, encoding="utf-8")
        manifest[size] = {
            "weeks": len(analysis["weekly_data"]),
            "repositories": repositories,
            "commits": commits,
            "prs": prs,
            "issues": prs // 2,
            "htmlBytes": len(html.encode("utf-8")),
            "displayedPrs": len(analysis["recent_prs"]),
            "displayedCommits": len(analysis["recent_commits"]),
        }
    (output / "fixtures.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
