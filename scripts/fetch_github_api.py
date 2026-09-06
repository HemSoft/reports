import subprocess
import json
from datetime import datetime
from zoneinfo import ZoneInfo

EDT = ZoneInfo("America/New_York")
START_DATE = datetime(2026, 6, 13, 0, 0, 0, tzinfo=EDT)
START_UTC = START_DATE.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")

# 1. Fetch PRs created or updated in HemSoft org or by HemSoft
print("Fetching PRs...")
pr_cmd = [
    "gh",
    "search",
    "prs",
    "user:HemSoft created:>=2026-06-13",
    "--limit",
    "100",
    "--json",
    "number,title,state,repository,createdAt,closedAt,url,author,labels,commentsCount",
]
pr_res = subprocess.run(pr_cmd, capture_output=True, text=True, errors="replace")
prs = json.loads(pr_res.stdout) if pr_res.returncode == 0 else []
print(f"Found {len(prs)} PRs created since 2026-06-13.")

# 2. Fetch Issues created or updated
print("Fetching Issues...")
issue_cmd = [
    "gh",
    "search",
    "issues",
    "user:HemSoft created:>=2026-06-13",
    "--limit",
    "100",
    "--json",
    "number,title,state,repository,createdAt,closedAt,url,author,labels,commentsCount",
]
issue_res = subprocess.run(issue_cmd, capture_output=True, text=True, errors="replace")
issues = json.loads(issue_res.stdout) if issue_res.returncode == 0 else []
print(f"Found {len(issues)} Issues created since 2026-06-13.")

# 3. Check all repos in HemSoft for remote commits
print("Fetching repos list...")
repos_cmd = [
    "gh",
    "repo",
    "list",
    "HemSoft",
    "--limit",
    "100",
    "--json",
    "name,isPrivate,description,pushedAt,stargazerCount,forkCount,primaryLanguage",
]
repos_res = subprocess.run(repos_cmd, capture_output=True, text=True, errors="replace")
all_repos = json.loads(repos_res.stdout) if repos_res.returncode == 0 else []

print(f"Total repos: {len(all_repos)}")
remote_only = []
for r in all_repos:
    pushed = r.get("pushedAt")
    if pushed and pushed >= START_UTC:
        remote_only.append(r["name"])

print(f"Repos with pushes since {START_UTC}: {len(remote_only)}")
print("List:", ", ".join(remote_only))
