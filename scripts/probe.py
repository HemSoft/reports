import os
import subprocess

base_dir = r"D:\github\HemSoft"
print(f"Scanning base directory: {base_dir}")

local_repos = []
for item in os.listdir(base_dir):
    full_path = os.path.join(base_dir, item)
    if os.path.isdir(full_path):
        git_dir = os.path.join(full_path, ".git")
        if os.path.exists(git_dir) or os.path.isfile(git_dir):
            local_repos.append((item, full_path))

print(f"Found {len(local_repos)} local git repositories/worktrees.")

commits_by_repo = {}
total_commits = 0

for name, path in local_repos:
    try:
        cmd = [
            "git",
            "-C",
            path,
            "log",
            "--all",
            "--since=2026-06-13T00:00:00",
            "--format=%H%x09%an%x09%ae%x09%aI%x09%cn%x09%ce%x09%cI%x09%s",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", check=True)
        lines = [line for line in res.stdout.strip().split("\n") if line.strip()]
        if lines:
            commits_by_repo[name] = len(lines)
            total_commits += len(lines)
    except Exception:
        pass

print(f"Total commits in past 12 weeks across local repos: {total_commits}")
print("Top 15 repos by commit count:")
for name, cnt in sorted(commits_by_repo.items(), key=lambda x: x[1], reverse=True)[:15]:
    print(f"  {name}: {cnt}")
