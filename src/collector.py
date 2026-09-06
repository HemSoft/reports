import os
import sys
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

EDT = ZoneInfo("America/New_York")

COMMAND_TIMEOUT_SECONDS = 120


class CollectionError(RuntimeError):
    """A required source could not be collected completely."""


def _run_command(cmd, source):
    try:
        result = subprocess.run(
            cmd, capture_output=True, encoding="utf-8", errors="replace",
            check=True, timeout=COMMAND_TIMEOUT_SECONDS,
        )
        # Check explicitly as well so alternate runners cannot return failed data.
        if result.returncode:
            raise subprocess.CalledProcessError(
                result.returncode, cmd, output=result.stdout, stderr=result.stderr)
        return result.stdout
    except subprocess.TimeoutExpired as exc:
        raise CollectionError(f"{source}: timed out after {COMMAND_TIMEOUT_SECONDS}s") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "command failed").strip()
        raise CollectionError(f"{source}: exit {exc.returncode}: {detail}") from exc
    except OSError as exc:
        raise CollectionError(f"{source}: {exc}") from exc


REPO_FIELDS = {
    "name": (str,), "nameWithOwner": (str,), "isPrivate": (bool,), "description": (str, type(None)),
    "stargazerCount": (int,), "forkCount": (int,),
    "primaryLanguage": (dict, type(None)),
}
PR_FIELDS = {
    "number": (int,), "title": (str,), "state": (str,), "createdAt": (str,),
    "closedAt": (str, type(None)), "mergedAt": (str, type(None)), "url": (str,),
}
ISSUE_FIELDS = {key: value for key, value in PR_FIELDS.items() if key != "mergedAt"}


def _validate_item(item, fields):
    if not isinstance(item, dict):
        raise ValueError("expected an object")
    for key, allowed in fields.items():
        if key not in item or type(item[key]) not in allowed:
            raise ValueError(f"missing or invalid {key}")
    for key in ("name", "title", "url"):
        if key in fields and not item[key]:
            raise ValueError(f"empty {key}")
    for key in ("number", "stargazerCount", "forkCount"):
        if key in fields and item[key] < (1 if key == "number" else 0):
            raise ValueError(f"invalid {key}")
    language = item.get("primaryLanguage")
    if language is not None and (not isinstance(language.get("name"), str) or not language["name"]):
        raise ValueError("invalid primaryLanguage.name")
    for key in ("createdAt", "mergedAt", "closedAt"):
        if key in fields and item[key] is not None:
            parsed = datetime.fromisoformat(item[key].replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError(f"{key} lacks a timezone")
    if "state" in fields:
        states = ("OPEN", "CLOSED", "MERGED") if "mergedAt" in fields else ("OPEN", "CLOSED")
        if item["state"] not in states:
            raise ValueError("invalid state")
        if item["state"] in ("CLOSED", "MERGED") and not item["closedAt"]:
            raise ValueError("closed record lacks closedAt")
        if item["state"] == "MERGED" and not item["mergedAt"]:
            raise ValueError("merged pull request lacks mergedAt")


def _read_connection(query, variables, source, fields, identity):
    """Read every page, rejecting partial GraphQL data and changing listings."""
    items = []
    seen_ids, seen_cursors = set(), set()
    cursor = None
    expected_count = None
    while True:
        cmd = ["gh", "api", "graphql", "-f", f"query={query}"]
        for key, value in variables.items():
            cmd.extend(["-f", f"{key}={value}"])
        if cursor is not None:
            cmd.extend(["-f", f"cursor={cursor}"])
        try:
            payload = json.loads(_run_command(cmd, source))
            if payload.get("errors"):
                raise ValueError("GraphQL returned errors; partial data rejected")
            connection = payload["data"]["scope"]["items"]
            nodes, page = connection["nodes"], connection["pageInfo"]
            count = connection["totalCount"]
            if type(count) is not int or count < 0 or not isinstance(nodes, list):
                raise ValueError("invalid connection count or nodes")
            if expected_count is None:
                expected_count = count
            if count != expected_count:
                raise ValueError("listing changed during collection; refresh required")
            for item in nodes:
                _validate_item(item, fields)
                key = item[identity]
                if key in seen_ids:
                    raise ValueError("duplicate record across pages; refresh required")
                seen_ids.add(key)
                items.append(item)
            if type(page["hasNextPage"]) is not bool:
                raise ValueError("invalid hasNextPage")
            if not page["hasNextPage"]:
                if len(items) != expected_count:
                    raise ValueError("incomplete enumeration: record count differs from totalCount")
                return items
            cursor = page["endCursor"]
            if (not isinstance(cursor, str) or not cursor or cursor in seen_cursors
                    or not nodes or len(items) >= expected_count):
                raise ValueError("incomplete enumeration: pagination made no progress")
            seen_cursors.add(cursor)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise CollectionError(f"{source}: invalid JSON response: {exc}") from exc


REPOSITORIES_QUERY = """
query($owner: String!, $cursor: String) {
  scope: repositoryOwner(login: $owner) {
    items: repositories(first: 100, after: $cursor, ownerAffiliations: [OWNER]) {
      totalCount pageInfo { hasNextPage endCursor }
      nodes { name nameWithOwner isPrivate description stargazerCount forkCount primaryLanguage { name } }
    }
  }
}
"""


def list_github_repositories():
    records = _read_connection(REPOSITORIES_QUERY, {"owner": "HemSoft"},
                               "GitHub repository enumeration for HemSoft", REPO_FIELDS, "nameWithOwner")
    for item in records:
        canonical = item["nameWithOwner"]
        if canonical.lower() != f"HemSoft/{item['name']}".lower():
            raise CollectionError(f"GitHub repository enumeration: invalid canonical identity {canonical}")
    return {item["name"]: item for item in records}


def _repository_activity(canonical, connection, fields, source):
    owner, name = canonical.split("/", 1)
    query = ("query($owner:String!, $name:String!, $cursor:String) { "
             "scope:repository(owner:$owner, name:$name) { items:" + connection +
             "(first:100, after:$cursor) { totalCount pageInfo { hasNextPage endCursor } nodes { " +
             " ".join(fields) + " } } } }")
    return _read_connection(query, {"owner": owner, "name": name}, source, fields, "number")


def _write_cache(cache_file, data):
    directory = os.path.dirname(os.path.abspath(cache_file))
    os.makedirs(directory, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,
                                         delete=False) as stream:
            temporary = stream.name
            json.dump(data, stream, indent=2)
        os.replace(temporary, cache_file)
    finally:
        if temporary and os.path.exists(temporary):
            os.remove(temporary)


def get_date_range(weeks=12, start_str=None, end_str=None):
    if weeks <= 0:
        raise ValueError("weeks must be positive")
    if (start_str is None) != (end_str is None):
        raise ValueError("--start and --end must be supplied together")
    if start_str is not None:
        start_dt = datetime.strptime(start_str, "%Y-%m-%d").replace(hour=0, minute=0, second=0, tzinfo=EDT)
        end_dt = datetime.strptime(end_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=EDT)
    else:
        end_dt = datetime.now(EDT).replace(hour=23, minute=59, second=59, microsecond=0)
        start_dt = (end_dt - timedelta(weeks=weeks)).replace(hour=0, minute=0, second=0, microsecond=0)
    if start_dt > end_dt:
        raise ValueError("start date must not be after end date")
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
    
    try:
        candidate_dirs = [os.path.join(base_dir, d) for d in os.listdir(base_dir)
                          if os.path.isdir(os.path.join(base_dir, d))]
    except OSError as exc:
        raise CollectionError(f"Repository enumeration in {base_dir}: {exc}") from exc
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
            output = _run_command(cmd, f"Git history in {d}")
            
            cur = None
            for line in output.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if line.startswith("COMMIT_META\t"):
                    parts = line.split("\t", 8)
                    if len(parts) != 9:
                        raise ValueError("invalid commit metadata")
                    chash = parts[1]
                    if chash in seen_hashes:
                        cur = None
                        continue
                    seen_hashes.add(chash)
                    
                    try:
                        dt_orig = datetime.fromisoformat(parts[4])
                        if dt_orig.tzinfo is None:
                            raise ValueError("author date lacks a timezone")
                        dt_edt = dt_orig.astimezone(EDT)
                    except (ValueError, TypeError) as exc:
                        raise CollectionError(f"Git history in {d}: invalid author date") from exc
                    
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
        except (ValueError, IndexError) as exc:
            raise CollectionError(f"Git history in {d}: malformed output: {exc}") from exc

    for c in commits:
        c["category"] = classify_commit(c["subject"], c["files"])
        c["net_lines"] = c["additions"] - c["deletions"]
        
    return sorted(commits, key=lambda x: x["author_date"], reverse=True)

def collect_github_metadata(active_repo_names, start_dt, end_dt):
    # The legacy positional argument is retained for callers; GitHub owns discovery.
    repo_meta = list_github_repositories()
    prs_by_repo = defaultdict(list)
    issues_by_repo = defaultdict(list)
    for r, meta in repo_meta.items():
        canonical = meta["nameWithOwner"]
        for item in _repository_activity(canonical, "pullRequests", PR_FIELDS,
                                         f"GitHub pull requests for {canonical}"):
            if not _has_event(item, ("createdAt", "mergedAt", "closedAt"), start_dt, end_dt):
                continue
            item["cycle_hours"] = None
            if item["mergedAt"]:
                created = datetime.fromisoformat(item["createdAt"].replace("Z", "+00:00"))
                merged = datetime.fromisoformat(item["mergedAt"].replace("Z", "+00:00"))
                item["cycle_hours"] = round((merged - created).total_seconds() / 3600.0, 2)
            item["repo"] = r
            prs_by_repo[r].append(item)
        for item in _repository_activity(canonical, "issues", ISSUE_FIELDS,
                                         f"GitHub issues for {canonical}"):
            if _has_event(item, ("createdAt", "closedAt"), start_dt, end_dt):
                item["repo"] = r
                issues_by_repo[r].append(item)
    return repo_meta, dict(prs_by_repo), dict(issues_by_repo)


def _has_event(item, keys, start, end):
    return any(item.get(key) and start.astimezone(timezone.utc) <=
               datetime.fromisoformat(item[key].replace("Z", "+00:00")).astimezone(timezone.utc) <=
               end.astimezone(timezone.utc) for key in keys)


def collect_all(base_dir, weeks=12, start_str=None, end_str=None, cache_file=None, refresh=False):
    start_dt, end_dt = get_date_range(weeks, start_str, end_str)
    
    if cache_file and not refresh and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                cached_start = data.get("range", {}).get("start_iso")
                cached_end = data.get("range", {}).get("end_iso")
                if (data.get("collection_complete") is True
                        and data.get("collection_scope") == "all-owned-paginated-v1"
                        and cached_start == start_dt.isoformat()
                        and cached_end == end_dt.isoformat()):
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
        "collection_complete": True,
        "collection_scope": "all-owned-paginated-v1",
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
        _write_cache(cache_file, data)
        print(f"Saved audit data cache to {cache_file}")
        
    return data

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="List every accessible HemSoft-owned repository.")
    parser.add_argument("--list-repositories", action="store_true", required=True)
    parser.parse_args()
    try:
        for repository in list_github_repositories().values():
            print(repository["nameWithOwner"])
    except CollectionError as exc:
        print(f"Collection failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
