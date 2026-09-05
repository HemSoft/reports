import subprocess
import json

# Get all repos of HemSoft
cmd = ["gh", "repo", "list", "HemSoft", "--limit", "100", "--json", "name,isPrivate,description,pushedAt,createdAt,updatedAt,defaultBranchRef,stargazerCount,forkCount"]
res = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
remote_repos = json.loads(res.stdout)

print(f"Total remote repos for HemSoft: {len(remote_repos)}")
recent_remote = [r for r in remote_repos if r.get("pushedAt") and r.get("pushedAt") >= "2026-06-13"]
print(f"Remote repos with pushed_at >= 2026-06-13: {len(recent_remote)}")
for r in sorted(recent_remote, key=lambda x: x["pushedAt"], reverse=True):
    print(f"  {r['name']} (pushedAt: {r['pushedAt']}, private: {r['isPrivate']})")
