"""Local source/secret checks plus executable-dependency policy validation."""

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def check_policy():
    """Reject mutable external actions and excess Pages job permissions."""
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        workflow = yaml.safe_load(path.read_text())
        references = re.findall(r"^\s*-?\s*uses:\s*(\S+)", path.read_text(), re.M)
        for reference in references:
            if not reference.startswith("./") and not re.fullmatch(
                r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", reference
            ):
                raise ValueError(f"Mutable action reference in {path.name}: {reference}")
        for name, job in workflow["jobs"].items():
            permissions = job.get("permissions", workflow.get("permissions", {}))
            expected = (
                {"pages": "write", "id-token": "write"}
                if path.name == "pages.yml" and name == "deploy"
                else {"contents": "read"}
            )
            if permissions != expected:
                raise ValueError(f"Unexpected permissions in {path.name}/{name}")


def scan_secrets():
    """Scan tracked files without network verification; never print secret values."""
    result = subprocess.run(
        [sys.executable, "-m", "detect_secrets", "scan", "--no-verify"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    findings = json.loads(result.stdout)["results"]
    for filename, items in findings.items():
        for item in items:
            print(f"Potential secret: {filename}:{item['line_number']} ({item['type']})")
    if findings:
        raise ValueError("Secret scan requires investigation")
    print("Secret scan: no findings in tracked files (network verification disabled)")


def main():
    check_policy()
    scan_secrets()
    subprocess.run(
        [sys.executable, "-m", "bandit", "-r", "src", "scripts", "cli.py", "-ll"],
        cwd=ROOT,
        check=True,
        timeout=120,
    )
    print("Security policy and local source checks: PASS")


if __name__ == "__main__":
    main()
