import os
import json
import statistics
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict, Counter

from src.github_identity import repository_identity

EDT = ZoneInfo("America/New_York")


def _in_interval(timestamp, start, end):
    if not timestamp:
        return False
    event = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return (
        start.astimezone(timezone.utc)
        <= event.astimezone(timezone.utc)
        <= end.astimezone(timezone.utc)
    )


def _canonical_commits(commits, repo_meta):
    return [
        dict(
            commit,
            github_repository=repository_identity(
                commit["repo"], repo_meta.get(commit["repo"], {}).get("nameWithOwner")
            ),
        )
        for commit in commits
    ]


def analyze_data(data):
    repo_meta = data.get("repo_meta", {})
    commits = _canonical_commits(data.get("commits", []), repo_meta)
    prs_by_repo = data.get("prs", {})
    issues_by_repo = data.get("issues", {})
    range_info = data.get("range", {})

    start_dt = datetime.fromisoformat(range_info["start_iso"]).astimezone(EDT)
    end_dt = datetime.fromisoformat(range_info["end_iso"]).astimezone(EDT)
    if start_dt > end_dt:
        raise ValueError("start date must not be after end date")

    # 1. Commits aggregates
    total_commits = len(commits)
    total_additions = sum(c["additions"] for c in commits)
    total_deletions = sum(c["deletions"] for c in commits)
    net_lines = total_additions - total_deletions

    # Files touched
    all_files = set()
    for c in commits:
        for f in c.get("files", []):
            all_files.add((c["repo"], f["path"]))
    total_unique_files = len(all_files)

    # Author categories
    author_counts = Counter(c["author_category"] for c in commits)

    # Commit categories
    category_counts = Counter(c["category"] for c in commits)

    # 2. PRs aggregates
    all_prs = []
    for r_prs in prs_by_repo.values():
        all_prs.extend(r_prs)
    total_prs = len(all_prs)
    merged_prs = [p for p in all_prs if p.get("state") == "MERGED"]
    open_prs = [p for p in all_prs if p.get("state") == "OPEN"]

    pr_merge_rate = round((len(merged_prs) / total_prs * 100.0), 1) if total_prs > 0 else 0.0

    # Cycle times for merged PRs
    cycle_times = [p["cycle_hours"] for p in merged_prs if p.get("cycle_hours") is not None]
    avg_cycle_time = round(sum(cycle_times) / len(cycle_times), 2) if cycle_times else 0.0
    median_cycle_time = round(statistics.median(cycle_times), 2) if cycle_times else 0.0

    cycle_distribution = {
        "under_1h": sum(1 for t in cycle_times if t < 1.0),
        "1h_to_4h": sum(1 for t in cycle_times if 1.0 <= t < 4.0),
        "4h_to_24h": sum(1 for t in cycle_times if 4.0 <= t < 24.0),
        "1d_to_3d": sum(1 for t in cycle_times if 24.0 <= t < 72.0),
        "over_3d": sum(1 for t in cycle_times if t >= 72.0),
    }

    # 3. Issues aggregates
    all_issues = []
    for r_issues in issues_by_repo.values():
        all_issues.extend(r_issues)
    total_issues = len(all_issues)
    closed_issues = [i for i in all_issues if i.get("state") == "CLOSED"]
    open_issues = [i for i in all_issues if i.get("state") == "OPEN"]
    issue_close_rate = (
        round((len(closed_issues) / total_issues * 100.0), 1) if total_issues > 0 else 0.0
    )

    # 4. Temporal analysis & Day/Hour matrices
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_counts = {d: 0 for d in day_names}
    hour_counts = {h: 0 for h in range(24)}
    matrix_7x24 = [[0 for _ in range(24)] for _ in range(7)]

    commits_by_date = defaultdict(list)
    for c in commits:
        d_idx = c["day_index"]
        h = c["hour"]
        day_counts[c["day_of_week"]] += 1
        hour_counts[h] += 1
        matrix_7x24[d_idx][h] += 1
        commits_by_date[c["date_str"]].append(c)

    # Active days and streaks
    cur_d = start_dt.date()
    end_d = end_dt.date()
    total_calendar_days = (end_d - cur_d).days + 1

    active_days_set = set(commits_by_date.keys())
    active_days_count = len(active_days_set)
    active_days_pct = round((active_days_count / total_calendar_days * 100.0), 1)

    # Calculate longest and current streak
    all_dates = [cur_d + timedelta(days=i) for i in range(total_calendar_days)]
    streaks = []
    current_running_streak = 0
    for d in all_dates:
        d_str = d.strftime("%Y-%m-%d")
        if d_str in active_days_set:
            current_running_streak += 1
        else:
            if current_running_streak > 0:
                streaks.append(current_running_streak)
            current_running_streak = 0
    if current_running_streak > 0:
        streaks.append(current_running_streak)

    longest_streak = max(streaks) if streaks else 0

    # Check current streak from end date backwards
    current_streak = 0
    for d in reversed(all_dates):
        d_str = d.strftime("%Y-%m-%d")
        if d_str in active_days_set:
            current_streak += 1
        else:
            break

    # Peak day
    peak_day_str = (
        max(commits_by_date.items(), key=lambda x: len(x[1]))[0] if commits_by_date else "N/A"
    )
    peak_day_commits = len(commits_by_date[peak_day_str]) if peak_day_str != "N/A" else 0
    peak_day_adds = sum(c["additions"] for c in commits_by_date.get(peak_day_str, []))

    # Day-parts
    morning = sum(hour_counts[h] for h in range(6, 12))
    afternoon = sum(hour_counts[h] for h in range(12, 18))
    evening = sum(hour_counts[h] for h in range(18, 22))
    night_owl = sum(hour_counts[h] for h in [22, 23, 0, 1, 2, 3, 4, 5])

    weekend_commits = day_counts["Saturday"] + day_counts["Sunday"]
    weekday_commits = total_commits - weekend_commits
    weekend_ratio = (
        round((weekend_commits / total_commits * 100.0), 1) if total_commits > 0 else 0.0
    )
    night_owl_ratio = round((night_owl / total_commits * 100.0), 1) if total_commits > 0 else 0.0

    peak_hour = max(hour_counts.items(), key=lambda x: x[1])[0]
    peak_day_name = max(day_counts.items(), key=lambda x: x[1])[0]

    # 5. Calendar-week buckets, including the final partial week.
    weekly_data = []

    w_start = start_dt
    w = 1
    while w_start <= end_dt:
        next_start = w_start + timedelta(days=7)
        w_end = min(next_start - timedelta(microseconds=1), end_dt)
        w_start_str = w_start.strftime("%Y-%m-%d")
        w_end_str = w_end.strftime("%Y-%m-%d")

        w_commits = [c for c in commits if _in_interval(c["author_date"], w_start, w_end)]
        w_prs_merged = [p for p in merged_prs if _in_interval(p.get("mergedAt"), w_start, w_end)]
        w_prs_opened = [p for p in all_prs if _in_interval(p.get("createdAt"), w_start, w_end)]
        w_issues_closed = [
            i for i in closed_issues if _in_interval(i.get("closedAt"), w_start, w_end)
        ]

        w_adds = sum(c["additions"] for c in w_commits)
        w_dels = sum(c["deletions"] for c in w_commits)
        w_net = w_adds - w_dels

        w_active_days = len(set(c["date_str"] for c in w_commits))
        w_repo_counts = Counter(c["repo"] for c in w_commits)
        w_top_repo = w_repo_counts.most_common(1)[0][0] if w_repo_counts else "None"

        weekly_data.append(
            {
                "week_num": w,
                "label": f"Week {w:02d}",
                "range_str": f"{w_start.strftime('%b %d')} - {w_end.strftime('%b %d')}",
                "start_date": w_start_str,
                "end_date": w_end_str,
                "commits": len(w_commits),
                "additions": w_adds,
                "deletions": w_dels,
                "net_lines": w_net,
                "prs_opened": len(w_prs_opened),
                "prs_merged": len(w_prs_merged),
                "issues_closed": len(w_issues_closed),
                "active_days": w_active_days,
                "top_repo": w_top_repo,
                "human_commits": sum(
                    1 for c in w_commits if c["author_category"] == "Human (Franz Hemmer)"
                ),
                "ai_commits": sum(1 for c in w_commits if "AI" in c["author_category"]),
            }
        )

        w_start = next_start
        w += 1

    # 6. Repository Profiles
    repo_groups = defaultdict(list)
    for c in commits:
        repo_groups[c["repo"]].append(c)

    repo_profiles = []
    active_repos = set(repo_groups) | set(prs_by_repo) | set(issues_by_repo)
    for r_name in sorted(active_repos):
        r_commits = repo_groups[r_name]
        meta = repo_meta.get(r_name, {})
        r_prs = prs_by_repo.get(r_name, [])
        r_issues = issues_by_repo.get(r_name, [])

        r_merged_prs = sum(1 for p in r_prs if p.get("state") == "MERGED")
        r_closed_issues = sum(1 for i in r_issues if i.get("state") == "CLOSED")

        r_adds = sum(c["additions"] for c in r_commits)
        r_dels = sum(c["deletions"] for c in r_commits)
        r_net = r_adds - r_dels

        # Languages in this repo
        r_langs = Counter()
        for c in r_commits:
            for f in c.get("files", []):
                r_langs[f["language"]] += f["adds"] + f["dels"]
        metadata_language = (meta.get("primaryLanguage") or {}).get("name") or "Unknown"
        primary_lang = r_langs.most_common(1)[0][0] if r_langs else metadata_language

        r_active_days = len(set(c["date_str"] for c in r_commits))
        first_commit = min((c["author_date"] for c in r_commits), default=None)
        last_commit = max((c["author_date"] for c in r_commits), default=None)

        repo_profiles.append(
            {
                "name": r_name,
                "github_repository": repository_identity(r_name, meta.get("nameWithOwner")),
                "description": meta.get("description") or "Repository",
                "is_private": meta.get("isPrivate", True),
                "stars": meta.get("stargazerCount", 0),
                "forks": meta.get("forkCount", 0),
                "primary_language": primary_lang,
                "commits": len(r_commits),
                "commits_share": round(len(r_commits) / total_commits * 100.0, 1)
                if total_commits
                else 0.0,
                "additions": r_adds,
                "deletions": r_dels,
                "net_lines": r_net,
                "prs_total": len(r_prs),
                "prs_merged": r_merged_prs,
                "issues_total": len(r_issues),
                "issues_closed": r_closed_issues,
                "active_days": r_active_days,
                "first_commit": first_commit,
                "last_commit": last_commit,
            }
        )

    repo_profiles.sort(key=lambda x: x["commits"], reverse=True)

    # 7. Language Breakdown
    lang_stats = defaultdict(lambda: {"adds": 0, "dels": 0, "files": set(), "commits": set()})
    for c in commits:
        for f in c.get("files", []):
            lang = f["language"]
            lang_stats[lang]["adds"] += f["adds"]
            lang_stats[lang]["dels"] += f["dels"]
            lang_stats[lang]["files"].add((c["repo"], f["path"]))
            lang_stats[lang]["commits"].add(c["hash"])

    language_breakdown = []
    for lang, s in lang_stats.items():
        total_churn = s["adds"] + s["dels"]
        language_breakdown.append(
            {
                "language": lang,
                "additions": s["adds"],
                "deletions": s["dels"],
                "net_lines": s["adds"] - s["dels"],
                "total_churn": total_churn,
                "files_count": len(s["files"]),
                "commits_count": len(s["commits"]),
            }
        )
    language_breakdown.sort(key=lambda x: x["total_churn"], reverse=True)

    # Return consolidated analytical report
    return {
        "generated_at": data.get("generated_at"),
        "range": range_info,
        "kpis": {
            "total_commits": total_commits,
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "net_lines": net_lines,
            "total_unique_files": total_unique_files,
            "total_prs": total_prs,
            "merged_prs": len(merged_prs),
            "open_prs": len(open_prs),
            "pr_merge_rate": pr_merge_rate,
            "avg_pr_cycle_hours": avg_cycle_time,
            "median_pr_cycle_hours": median_cycle_time,
            "pr_cycle_distribution": cycle_distribution,
            "total_issues": total_issues,
            "closed_issues": len(closed_issues),
            "open_issues": len(open_issues),
            "issue_close_rate": issue_close_rate,
            "active_repos_count": len(repo_profiles),
            "total_calendar_days": total_calendar_days,
            "active_days_count": active_days_count,
            "active_days_pct": active_days_pct,
            "longest_streak": longest_streak,
            "current_streak": current_streak,
            "avg_commits_per_active_day": round(total_commits / active_days_count, 1)
            if active_days_count > 0
            else 0,
            "avg_commits_per_day": round(total_commits / total_calendar_days, 1),
            "peak_day": {
                "date": peak_day_str,
                "commits": peak_day_commits,
                "additions": peak_day_adds,
            },
            "peak_hour_edt": peak_hour,
            "peak_day_name": peak_day_name,
            "day_parts": {
                "morning": morning,
                "afternoon": afternoon,
                "evening": evening,
                "night_owl": night_owl,
            },
            "night_owl_ratio": night_owl_ratio,
            "weekend_commits": weekend_commits,
            "weekday_commits": weekday_commits,
            "weekend_ratio": weekend_ratio,
        },
        "author_distribution": dict(author_counts),
        "category_distribution": dict(category_counts),
        "weekly_data": weekly_data,
        "repo_profiles": repo_profiles,
        "language_breakdown": language_breakdown,
        "temporal": {
            "day_counts": day_counts,
            "hour_counts": hour_counts,
            "matrix_7x24": matrix_7x24,
            "day_names": day_names,
        },
        "recent_prs": sorted(all_prs, key=lambda x: x.get("createdAt", ""), reverse=True)[:50],
        "recent_commits": commits[:100],
    }


if __name__ == "__main__":
    cache_path = os.path.join(os.path.dirname(__file__), "..", "data", "cache_12weeks.json")
    with open(cache_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    results = analyze_data(raw_data)
    print("--- EXECUTIVE PRODUCTIVITY KPIs ---")
    for k, v in results["kpis"].items():
        if isinstance(v, dict):
            print(f"  {k}: {v}")
        else:
            print(f"  {k}: {v:,}" if isinstance(v, (int, float)) else f"  {k}: {v}")
