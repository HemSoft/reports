import os
import sys
import json
import re
import subprocess
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

EDT = ZoneInfo("America/New_York")

def get_date_range(weeks=12, start_str=None, end_str=None):
    if start_str and end_str:
        start_dt = datetime.strptime(start_str, "%Y-%m-%d").replace(hour=0, minute=0, second=0, tzinfo=EDT)
        end_dt = datetime.strptime(end_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=EDT)
    else:
        end_dt = datetime.now(EDT).replace(hour=23, minute=59, second=59, microsecond=0)
        start_dt = (end_dt - timedelta(weeks=weeks)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start_dt, end_dt

def detect_language(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    base = os.path.basename(file_path).lower()
    
    mapping = {
        ".swift": "Swift",
        ".ts": "TypeScript",
        ".tsx": "TypeScript (React)",
        ".js": "JavaScript",
        ".jsx": "JavaScript (React)",
        ".go": "Go",
        ".py": "Python",
        ".cs": "C#",
        ".sh": "Shell",
        ".bash": "Shell",
        ".ps1": "PowerShell",
        ".psm1": "PowerShell",
        ".json": "JSON",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".toml": "TOML",
        ".md": "Markdown",
        ".html": "HTML",
        ".css": "CSS",
        ".scss": "SCSS",
        ".sql": "SQL",
        ".rs": "Rust",
        ".c": "C",
        ".cpp": "C++",
        ".h": "C/C++ Header",
        ".proto": "Protobuf",
        ".lock": "Lockfile",
    }
    if base in ["dockerfile", "containerfile"]:
        return "Docker"
    if base in ["makefile", "gnumakefile"]:
        return "Makefile"
    return mapping.get(ext, "Other" if ext else "Config/Docs")

def classify_commit(subject, files):
    s = subject.lower().strip()
    
    if re.match(r"^feat(\(.*\))?:", s) or s.startswith("feature:"):
        return "Feature"
    if re.match(r"^fix(\(.*\))?:", s) or s.startswith("bug:") or "fix " in s or "fixes " in s or "bugfix" in s:
        return "Bug Fix"
    if re.match(r"^refactor(\(.*\))?:", s) or "refactor" in s:
        return "Refactoring"
    if re.match(r"^docs(\(.*\))?:", s) or "readme" in s or "doc:" in s or "documentation" in s:
        return "Documentation"
    if re.match(r"^test(\(.*\))?:", s) or "tests:" in s or "testing" in s or "coverage" in s:
        return "Testing"
    if re.match(r"^perf(\(.*\))?:", s) or "performance" in s or "speed" in s:
        return "Performance"
    if re.match(r"^ci(\(.*\))?:", s) or re.match(r"^build(\(.*\))?:", s) or "workflow" in s or "action" in s or "pipeline" in s:
        return "CI / DevOps"
    if re.match(r"^chore(\(.*\))?:", s) or "bump" in s or "upgrade" in s or "clean" in s or "pin" in s:
        return "Chore / Maintenance"
    
    if any(k in s for k in ["ralph", "loop", "agent", "minibot", "hermes", "conductor", "automation"]):
        return "Agent / Automation"
    
    all_paths = [f["path"].lower() for f in files]
    if all(p.endswith(".md") or "doc" in p for p in all_paths) and all_paths:
        return "Documentation"
    if any("test" in p for p in all_paths) and len(all_paths) <= 2:
        return "Testing"
    
    return "Feature"

def categorize_author(name, email):
    n = name.lower()
    e = email.lower()
    if "copilot" in n or "copilot" in e:
        return "AI Copilot"
    if "cursor" in n or "cursor" in e:
        return "AI Agent (Cursor)"
    if "dependabot" in n or "dependabot" in e:
        return "Dependabot"
    if "github-actions" in n or "action" in e:
        return "CI Bot"
    if "bot" in n or "bot" in e:
        return "Bot"
    return "Human (Franz Hemmer)"

def collect_commits(base_dir, start_dt, end_dt):
    start_str = start_dt.strftime("%Y-%m-%dT00:00:00")
    end_str = end_dt.strftime("%Y-%m-%dT23:59:59")
    
    candidate_dirs = [os.path.join(base_dir, d) for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    commits = []
    seen_hashes = set()
    
    for d in candidate_dirs:
        git_dir = os.path.join(d, ".git")
        if not (os.path.exists(git_dir) or os.path.isfile(git_dir)):
            continue
        
        folder_name = os.path.basename(d)
        repo_name = folder_name.replace(".worktrees", "").split("-identify-")[0]
        if repo_name.startswith("."):
            repo_name = repo_name.lstrip(".")
            if not repo_name:
                repo_name = "dot-github"
        
        try:
            cmd = [
                "git", "-C", d, "log", "--all",
                f"--since={start_str}",
                f"--until={end_str}",
                "--format=COMMIT_META%x09%H%x09%an%x09%ae%x09%aI%x09%cn%x09%ce%x09%cI%x09%s",
                "--numstat"
            ]
            res = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", check=True)
            
            cur = None
            for line in res.stdout.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if line.startswith("COMMIT_META\t"):
                    parts = line.split("\t")
                    chash = parts[1]
                    if chash in seen_hashes:
                        cur = None
                        continue
                    seen_hashes.add(chash)
                    
                    try:
                        dt_orig = datetime.fromisoformat(parts[4])
                        dt_edt = dt_orig.astimezone(EDT)
                    except Exception:
                        cur = None
                        continue
                    
                    if dt_edt < start_dt or dt_edt > end_dt:
                        cur = None
                        continue
                        
                    subj = parts[8] if len(parts) > 8 else ""
                    cur = {
                        "hash": chash,
                        "repo": repo_name,
                        "author_name": parts[2],
                        "author_email": parts[3],
                        "author_category": categorize_author(parts[2], parts[3]),
                        "author_date": dt_edt.isoformat(),
                        "timestamp": dt_edt.timestamp(),
                        "day_of_week": dt_edt.strftime("%A"),
                        "day_index": dt_edt.weekday(),
                        "hour": dt_edt.hour,
                        "date_str": dt_edt.strftime("%Y-%m-%d"),
                        "subject": subj,
                        "additions": 0,
                        "deletions": 0,
                        "files": []
                    }
                    commits.append(cur)
                elif cur and "\t" in line:
                    sp = line.split("\t")
                    if len(sp) >= 3:
                        add_s, del_s, fpath = sp[0], sp[1], sp[2]
                        adds = int(add_s) if add_s.isdigit() else 0
                        dels = int(del_s) if del_s.isdigit() else 0
                        lang = detect_language(fpath)
                        cur["additions"] += adds
                        cur["deletions"] += dels
                        cur["files"].append({
                            "path": fpath,
                            "adds": adds,
                            "dels": dels,
                            "language": lang
                        })
        except Exception:
            pass
            
    for c in commits:
        c["category"] = classify_commit(c["subject"], c["files"])
        c["net_lines"] = c["additions"] - c["deletions"]
        
    return sorted(commits, key=lambda x: x["author_date"], reverse=True)

def collect_github_metadata(active_repo_names, start_dt, end_dt):
    start_iso = start_dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso = end_dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # 1. Repo general info
    repo_meta = {}
    try:
        cmd = ["gh", "repo", "list", "HemSoft", "--limit", "100", "--json", "name,isPrivate,description,pushedAt,createdAt,stargazerCount,forkCount,primaryLanguage"]
        res = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
        if res.returncode == 0:
            for r in json.loads(res.stdout):
                repo_meta[r["name"]] = r
    except Exception as e:
        print(f"Error fetching repo list: {e}")
        
    prs_by_repo = defaultdict(list)
    issues_by_repo = defaultdict(list)
    
    for r in active_repo_names:
        # Fetch PRs
        try:
            p_cmd = [
                "gh", "pr", "list", "--repo", f"HemSoft/{r}",
                "--state", "all", "--limit", "500",
                "--json", "number,title,state,createdAt,closedAt,mergedAt,url,headRefName,author,comments"
            ]
            p_res = subprocess.run(p_cmd, capture_output=True, encoding="utf-8", errors="replace")
            if p_res.returncode == 0 and p_res.stdout:
                items = json.loads(p_res.stdout)
                for item in items:
                    c_at = item.get("createdAt")
                    m_at = item.get("mergedAt")
                    cl_at = item.get("closedAt")
                    
                    # Check if within range
                    in_range = False
                    if c_at and start_iso <= c_at <= end_iso:
                        in_range = True
                    elif m_at and start_iso <= m_at <= end_iso:
                        in_range = True
                    elif cl_at and start_iso <= cl_at <= end_iso:
                        in_range = True
                        
                    if in_range:
                        # calculate cycle time in hours
                        cycle_hours = None
                        if m_at and c_at:
                            try:
                                dt_c = datetime.fromisoformat(c_at.replace("Z", "+00:00"))
                                dt_m = datetime.fromisoformat(m_at.replace("Z", "+00:00"))
                                cycle_hours = round((dt_m - dt_c).total_seconds() / 3600.0, 2)
                            except Exception:
                                pass
                        item["cycle_hours"] = cycle_hours
                        item["repo"] = r
                        prs_by_repo[r].append(item)
        except Exception:
            pass
            
        # Fetch Issues
        try:
            i_cmd = [
                "gh", "issue", "list", "--repo", f"HemSoft/{r}",
                "--state", "all", "--limit", "500",
                "--json", "number,title,state,createdAt,closedAt,url,author,labels,comments"
            ]
            i_res = subprocess.run(i_cmd, capture_output=True, encoding="utf-8", errors="replace")
            if i_res.returncode == 0 and i_res.stdout:
                items = json.loads(i_res.stdout)
                for item in items:
                    c_at = item.get("createdAt")
                    cl_at = item.get("closedAt")
                    
                    in_range = False
                    if c_at and start_iso <= c_at <= end_iso:
                        in_range = True
                    elif cl_at and start_iso <= cl_at <= end_iso:
                        in_range = True
                        
                    if in_range:
                        item["repo"] = r
                        issues_by_repo[r].append(item)
        except Exception:
            pass
            
    return repo_meta, dict(prs_by_repo), dict(issues_by_repo)

def collect_all(base_dir, weeks=12, start_str=None, end_str=None, cache_file=None):
    start_dt, end_dt = get_date_range(weeks, start_str, end_str)
    
    if cache_file and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                cached_start = data.get("range", {}).get("start_iso")
                cached_end = data.get("range", {}).get("end_iso")
                if cached_start == start_dt.isoformat() and cached_end == end_dt.isoformat():
                    print(f"Loaded cached audit data from {cache_file}")
                    return data
        except Exception as e:
            print(f"Cache read error: {e}")
            
    print(f"Scanning local commits in {base_dir} from {start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')} EDT...")
    commits = collect_commits(base_dir, start_dt, end_dt)
    print(f"Collected {len(commits)} unique commits.")
    
    # Active repos
    active_repos = sorted(list(set(c["repo"] for c in commits)))
    print(f"Active repos ({len(active_repos)}): {', '.join(active_repos)}")
    
    print("Collecting GitHub PRs, issues, and metadata...")
    repo_meta, prs, issues = collect_github_metadata(active_repos, start_dt, end_dt)
    
    data = {
        "generated_at": datetime.now(EDT).isoformat(),
        "range": {
            "weeks": weeks,
            "start_iso": start_dt.isoformat(),
            "end_iso": end_dt.isoformat(),
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "end_date": end_dt.strftime("%Y-%m-%d"),
            "start_formatted": start_dt.strftime("%b %d, %Y"),
            "end_formatted": end_dt.strftime("%b %d, %Y"),
        },
        "commits": commits,
        "prs": prs,
        "issues": issues,
        "repo_meta": repo_meta
    }
    
    if cache_file:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Saved audit data cache to {cache_file}")
        
    return data

if __name__ == "__main__":
    cache_path = os.path.join(os.path.dirname(__file__), "..", "data", "cache_12weeks.json")
    data = collect_all(r"D:\github\HemSoft", weeks=12, cache_file=cache_path)
    total_prs = sum(len(v) for v in data["prs"].values())
    total_issues = sum(len(v) for v in data["issues"].values())
    print(f"Done. Commits: {len(data['commits'])}, PRs: {total_prs}, Issues: {total_issues}")
