import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict

EDT = ZoneInfo("America/New_York")
START_DATE = datetime(2026, 6, 13, 0, 0, 0, tzinfo=EDT)
END_DATE = datetime(2026, 9, 5, 23, 59, 59, tzinfo=EDT)

START_ISO = START_DATE.isoformat()
END_ISO = END_DATE.isoformat()

print(
    f"Auditing period: {START_DATE.strftime('%Y-%m-%d %H:%M:%S %Z')} to {END_DATE.strftime('%Y-%m-%d %H:%M:%S %Z')}"
)

base_dir = r"D:\github\HemSoft"
candidate_dirs = [
    os.path.join(base_dir, d)
    for d in os.listdir(base_dir)
    if os.path.isdir(os.path.join(base_dir, d))
]

# Map canonical repo paths
repo_commits = defaultdict(list)
seen_hashes = set()

for d in candidate_dirs:
    git_dir = os.path.join(d, ".git")
    if not (os.path.exists(git_dir) or os.path.isfile(git_dir)):
        continue

    repo_name = os.path.basename(d)
    # If it's a worktree folder like .worktrees or has worktree in name, resolve to base repo name if possible
    base_name = repo_name.replace(".worktrees", "").split("-identify-")[0]

    # Run git log numstat
    try:
        cmd = [
            "git",
            "-C",
            d,
            "log",
            "--all",
            f"--since={START_DATE.strftime('%Y-%m-%dT00:00:00')}",
            f"--until={END_DATE.strftime('%Y-%m-%dT23:59:59')}",
            "--format=COMMIT_META%x09%H%x09%an%x09%ae%x09%aI%x09%cn%x09%ce%x09%cI%x09%s",
            "--numstat",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", check=True)

        current_commit = None
        for line in res.stdout.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("COMMIT_META\t"):
                parts = line.split("\t")
                chash = parts[1]
                if chash in seen_hashes:
                    current_commit = None
                    continue
                seen_hashes.add(chash)

                # Parse date to EDT
                dt = datetime.fromisoformat(parts[4])
                dt_edt = dt.astimezone(EDT)

                current_commit = {
                    "hash": chash,
                    "repo": base_name,
                    "author_name": parts[2],
                    "author_email": parts[3],
                    "date": dt_edt.isoformat(),
                    "committer_name": parts[5],
                    "committer_email": parts[6],
                    "committer_date": parts[7],
                    "subject": parts[8] if len(parts) > 8 else "",
                    "additions": 0,
                    "deletions": 0,
                    "files": [],
                }
                repo_commits[base_name].append(current_commit)
            elif current_commit and "\t" in line:
                stat_parts = line.split("\t")
                if len(stat_parts) >= 3:
                    add_str, del_str, fpath = stat_parts[0], stat_parts[1], stat_parts[2]
                    adds = int(add_str) if add_str.isdigit() else 0
                    dels = int(del_str) if del_str.isdigit() else 0
                    current_commit["additions"] += adds
                    current_commit["deletions"] += dels
                    current_commit["files"].append({"path": fpath, "adds": adds, "dels": dels})
    except Exception:
        # print(f"Error reading {d}: {e}")
        pass

print(f"Local repositories processed. Total unique commits collected: {len(seen_hashes)}")
for r, commits in sorted(repo_commits.items(), key=lambda x: len(x[1]), reverse=True):
    total_adds = sum(c["additions"] for c in commits)
    total_dels = sum(c["deletions"] for c in commits)
    print(f"  {r}: {len(commits)} commits (+{total_adds:,} / -{total_dels:,})")
