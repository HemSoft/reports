import subprocess
import json
from datetime import datetime
from zoneinfo import ZoneInfo

EDT = ZoneInfo("America/New_York")
START_ISO = "2026-06-13T00:00:00Z"

repos_cmd = ["gh", "repo", "list", "HemSoft", "--limit", "100", "--json", "name,isPrivate"]
repos_res = subprocess.run(repos_cmd, capture_output=True, text=True)
all_repos = json.loads(repos_res.stdout)

prs_by_repo = {}
issues_by_repo = {}

for r in all_repos:
    name = r["name"]
    # Check PRs
    p_cmd = [
        "gh", "pr", "list", "--repo", f"HemSoft/{name}",
        "--state", "all", "--limit", "100",
        "--json", "number,title,state,createdAt,closedAt,mergedAt,url,headRefName,baseRefName,author,labels,comments"
    ]
    p_res = subprocess.run(p_cmd, capture_output=True, encoding="utf-8", errors="replace")
    if p_res.returncode == 0 and p_res.stdout:
        try:
            repo_prs = json.loads(p_res.stdout)
            recent_prs = [p for p in repo_prs if p.get("createdAt", "") >= START_ISO or (p.get("mergedAt") and p.get("mergedAt") >= START_ISO)]
            if recent_prs:
                prs_by_repo[name] = recent_prs
        except Exception:
            pass

    # Check Issues
    i_cmd = [
        "gh", "issue", "list", "--repo", f"HemSoft/{name}",
        "--state", "all", "--limit", "100",
        "--json", "number,title,state,createdAt,closedAt,url,author,labels,comments"
    ]
    i_res = subprocess.run(i_cmd, capture_output=True, encoding="utf-8", errors="replace")
    if i_res.returncode == 0 and i_res.stdout:
        try:
            repo_issues = json.loads(i_res.stdout)
            recent_issues = [i for i in repo_issues if i.get("createdAt", "") >= START_ISO or (i.get("closedAt") and i.get("closedAt") >= START_ISO)]
            if recent_issues:
                issues_by_repo[name] = recent_issues
        except Exception:
            pass

total_prs = sum(len(v) for v in prs_by_repo.values())
total_issues = sum(len(v) for v in issues_by_repo.values())
print(f"Total PRs in 12-week window: {total_prs}")
for r, p_list in prs_by_repo.items():
    merged = sum(1 for p in p_list if p.get("state") == "MERGED")
    print(f"  {r}: {len(p_list)} PRs ({merged} merged)")

print(f"\nTotal Issues in 12-week window: {total_issues}")
for r, i_list in issues_by_repo.items():
    closed = sum(1 for i in i_list if i.get("state") == "CLOSED")
    print(f"  {r}: {len(i_list)} Issues ({closed} closed)")
