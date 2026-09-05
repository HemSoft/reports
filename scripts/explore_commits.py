import os
import subprocess
import json
from collections import defaultdict
from datetime import datetime

base_dir = r"D:\github\HemSoft"
repos = []

for item in os.listdir(base_dir):
    p = os.path.join(base_dir, item)
    if os.path.isdir(p):
        git_p = os.path.join(p, ".git")
        if os.path.exists(git_p) or os.path.isfile(git_p):
            repos.append((item, p))

print(f"Total candidate directories: {len(repos)}")

authors = defaultdict(int)
all_commits = {}  # hash -> commit_info to prevent duplicates from worktrees

for name, path in repos:
    try:
        # Get common git dir to identify worktrees
        c_dir_cmd = ["git", "-C", path, "rev-parse", "--git-common-dir"]
        common_dir = subprocess.check_output(c_dir_cmd, text=True, errors="replace").strip()
    except Exception:
        common_dir = path

    try:
        cmd = [
            "git", "-C", path, "log", "--all",
            "--since=2026-06-13T00:00:00",
            "--format=%H%x09%an%x09%ae%x09%aI%x09%cn%x09%ce%x09%cI%x09%s"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", check=True)
        for line in res.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 8:
                h, an, ae, ai, cn, ce, ci, s = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5], parts[6], "\t".join(parts[7:])
                authors[(an, ae)] += 1
                if h not in all_commits:
                    all_commits[h] = {
                        "hash": h,
                        "repo": name,
                        "common_dir": common_dir,
                        "author_name": an,
                        "author_email": ae,
                        "author_date": ai,
                        "committer_name": cn,
                        "committer_email": ce,
                        "committer_date": ci,
                        "subject": s
                    }
    except Exception as e:
        pass

print(f"Unique commits collected (deduped across worktrees): {len(all_commits)}")
print("\nAuthors found:")
for (an, ae), cnt in sorted(authors.items(), key=lambda x: x[1], reverse=True):
    print(f"  {an} <{ae}>: {cnt} commits")

commits_per_repo = defaultdict(int)
for c in all_commits.values():
    commits_per_repo[c["repo"]] += 1

print("\nUnique commits per primary repo:")
for r, cnt in sorted(commits_per_repo.items(), key=lambda x: x[1], reverse=True):
    print(f"  {r}: {cnt}")
